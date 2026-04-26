"""
Webhook module for Meta WhatsApp Cloud API.
Handles verification and incoming message processing.
"""
from datetime import date
from typing import Any, Dict, Optional
from fastapi import APIRouter, Query, Request, HTTPException, BackgroundTasks
from fastapi.responses import PlainTextResponse

from app.config import settings
from app.db import execute, fetch, fetchrow
from app.queue import set_user_state, get_user_state, clear_user_state
from app.whatsapp import send_text, ask_for_snooze_date
from app.logger import log_message
from app.date_parser import parse_user_date

router = APIRouter()


@router.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(alias="hub.mode"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
    hub_challenge: str = Query(alias="hub.challenge"),
) -> PlainTextResponse:
    """
    Handle Meta webhook verification handshake.
    Called when registering the webhook in Meta dashboard.
    """
    if hub_mode == "subscribe" and hub_verify_token == settings.wa_webhook_verify_token:
        return PlainTextResponse(hub_challenge)
    raise HTTPException(status_code=403, detail="Forbidden")


@router.post("/webhook", status_code=200)
async def receive_webhook(request: Request, background_tasks: BackgroundTasks) -> Dict[str, str]:
    """
    Receive incoming webhooks from Meta.
    Returns 200 immediately and processes in background to avoid timeouts.
    """
    body = await request.json()
    background_tasks.add_task(process_inbound, body)
    return {"status": "ok"}


async def process_inbound(body: Dict[str, Any]) -> None:
    """
    Process the inbound webhook payload.
    Extracts messages and routes to handlers.
    """
    try:
        entry = body.get("entry", [])
        if not entry:
            return

        changes = entry[0].get("changes", [])
        if not changes:
            return

        value = changes[0].get("value", {})

        # Skip if no messages (could be delivery status update)
        messages = value.get("messages", [])
        if not messages:
            return

        # Get contacts for profile info
        contacts = value.get("contacts", [])
        contact = contacts[0] if contacts else {}

        for msg in messages:
            try:
                await handle_inbound_message(msg, contact)
            except Exception as e:
                print(f"Error handling message: {e}")

    except Exception as e:
        print(f"Error processing inbound webhook: {e}")


async def handle_inbound_message(msg: Dict[str, Any], contact: Dict[str, Any]) -> None:
    """
    Route an inbound message to the appropriate handler.
    """
    phone = msg.get("from", "")
    user_name = contact.get("profile", {}).get("name", "there")

    msg_type = msg.get("type", "")

    if msg_type == "interactive":
        interactive = msg.get("interactive", {})
        if interactive.get("type") == "button_reply":
            reply_id = interactive.get("button_reply", {}).get("id", "")
            await handle_button_reply(phone, user_name, reply_id)

    elif msg_type == "text":
        text = msg.get("text", {}).get("body", "").strip()
        await handle_text_message(phone, user_name, text)


async def handle_button_reply(phone: str, user_name: str, reply_id: str) -> None:
    """
    Handle button reply interactions (Mark as Paid, Snooze).
    """
    if "_" not in reply_id:
        return

    action, payment_id_str = reply_id.split("_", 1)
    try:
        payment_id = int(payment_id_str)
    except ValueError:
        await send_text(phone, "❌ Invalid action. Please try again.")
        return

    if action == "paid":
        await mark_as_paid(payment_id, phone, user_name)
    elif action == "snooze":
        description = await get_payment_description(payment_id)
        if description:
            await set_user_state(phone, {"awaiting_snooze_for": payment_id})
            await ask_for_snooze_date(phone, description)
        else:
            await send_text(phone, "❌ Could not find that payment. It may have been deleted.")


async def handle_text_message(phone: str, user_name: str, text: str) -> None:
    """
    Handle text messages from users.
    """
    text_lower = text.lower()

    # Check if user is in snooze flow
    state = await get_user_state(phone)
    if state and "awaiting_snooze_for" in state:
        await handle_snooze_date(phone, user_name, text, state["awaiting_snooze_for"])
        return

    # Handle "paid" keyword
    if text_lower == "paid":
        row = await get_latest_pending_payment(phone)
        if row:
            await mark_as_paid(row["id"], phone, user_name)
        else:
            await send_text(
                phone,
                f"Hi {user_name}, I couldn't find any pending payments for your number. 🤔"
            )
        return

    # Default response
    await send_text(
        phone,
        "Please tap the *Mark as Paid* or *Remind me later* button from a reminder message, "
        "or reply *paid* to mark your latest payment as done."
    )


async def mark_as_paid(payment_id: int, phone: str, user_name: str) -> None:
    """
    Mark a payment as paid and notify the user.
    """
    # Get payment info before updating
    payment_row = await fetchrow(
        "SELECT description, user_id FROM payments WHERE id = $1",
        payment_id
    )

    if not payment_row:
        await send_text(phone, "❌ Payment not found. It may have been deleted.")
        return

    description = payment_row["description"]
    user_id = payment_row["user_id"]

    # Update payment status
    await execute(
        "UPDATE payments SET status = 'paid', updated_at = NOW() WHERE id = $1",
        payment_id
    )

    # Clear any conversation state
    await clear_user_state(phone)

    # Send confirmation
    await send_text(
        phone,
        f"✅ Got it, {user_name}! *{description}* has been marked as paid. Thank you! 🎉"
    )

    # Log the interaction
    await log_message(
        payment_id=payment_id,
        user_id=user_id,
        direction="inbound",
        message="User marked as paid",
    )


async def handle_snooze_date(
    phone: str,
    user_name: str,
    raw_text: str,
    payment_id: int
) -> None:
    """
    Process a snooze date from the user.
    """
    # Parse the date
    parsed = parse_user_date(raw_text)
    if parsed is None:
        await send_text(
            phone,
            "❌ Couldn't understand that date. Use *DD-MM-YYYY*, e.g. *25-06-2025*"
        )
        return

    snooze_date = parsed.date()

    # Check if date is in the past
    today = date.today()
    if snooze_date < today:
        await send_text(
            phone,
            "⚠️ That date is in the past. Please send a future date."
        )
        return

    # Get payment info
    payment_row = await fetchrow(
        "SELECT description, user_id FROM payments WHERE id = $1",
        payment_id
    )

    if not payment_row:
        await clear_user_state(phone)
        await send_text(phone, "❌ Payment not found. It may have been deleted.")
        return

    description = payment_row["description"]
    user_id = payment_row["user_id"]

    # Update payment with snooze date
    await execute(
        "UPDATE payments SET next_reminder_at = $1, status = 'snoozed', updated_at = NOW() WHERE id = $2",
        snooze_date,
        payment_id
    )

    # Clear conversation state
    await clear_user_state(phone)

    # Format date for display (e.g., "25 June 2025")
    friendly_date = f"{snooze_date.day} {snooze_date.strftime('%B')} {snooze_date.year}"

    # Send confirmation
    await send_text(
        phone,
        f"📅 Done! I'll remind you about *{description}* on *{friendly_date}*. 👍"
    )

    # Log the interaction
    await log_message(
        payment_id=payment_id,
        user_id=user_id,
        direction="inbound",
        message=f"Snoozed to {snooze_date}",
    )


async def get_payment_description(payment_id: int) -> Optional[str]:
    """
    Get the description for a payment.
    """
    row = await fetchrow(
        "SELECT description FROM payments WHERE id = $1",
        payment_id
    )
    return row["description"] if row else None


async def get_latest_pending_payment(phone: str) -> Optional[Dict[str, Any]]:
    """
    Get the most recent pending payment for a user by phone number.
    """
    row = await fetchrow(
        """
        SELECT p.id, p.description
        FROM payments p
        JOIN users u ON u.id = p.user_id
        WHERE u.phone = $1 AND p.status = 'pending'
        ORDER BY p.due_date ASC
        LIMIT 1
        """,
        phone
    )
    return row
