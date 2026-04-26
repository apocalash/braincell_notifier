"""
WhatsApp integration module.
Uses Meta Cloud API via httpx for sending messages.
"""
from datetime import datetime
from typing import Optional, Dict, Any
import httpx
from app.config import settings

# Shared async HTTP client
_http_client: Optional[httpx.AsyncClient] = None


def _get_client() -> httpx.AsyncClient:
    """Get or create the shared HTTP client."""
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(timeout=30.0)
    return _http_client


def _format_date(due_date: Any) -> str:
    """Format date for display."""
    if isinstance(due_date, str):
        due_date = datetime.strptime(due_date, "%Y-%m-%d").date()
    if hasattr(due_date, "strftime"):
        # %-d removes leading zero on some platforms, use manual formatting
        day = due_date.day
        month = due_date.strftime("%B")
        year = due_date.year
        return f"{day} {month} {year}"
    return str(due_date)


async def send_reminder(
    phone: str,
    payment: Dict[str, Any],
    first_name: str,
    days_label: str,
) -> str:
    """
    Send an interactive reminder message with quick-reply buttons.

    Args:
        phone: Phone number in international format without +
        payment: Dict with id, description, category, amount, due_date
        first_name: User's first name for greeting
        days_label: Human-readable days until due

    Returns:
        The WhatsApp message ID
    """
    # client = _get_client()
    # payment_id = payment["id"]
    # description = payment["description"]
    # category = payment.get("category", "Payment")
    # amount = payment["amount"]
    # due_date = _format_date(payment["due_date"])

    # url = f"https://graph.facebook.com/v19.0/{settings.wa_phone_number_id}/messages"

    # body = (
    #     f"Hi {first_name} 👋\n\n"
    #     f"*Payment Reminder*\n\n"
    #     f"📋 *{description}*\n"
    #     f"📂 Category: {category}\n"
    #     f"💰 Amount: ₹{amount:,.2f}\n"
    #     f"📅 Due: {due_date} ({days_label})\n\n"
    #     f"Tap a button below to respond."
    # )

    # payload = {
    #     "messaging_product": "whatsapp",
    #     "recipient_type": "individual",
    #     "to": phone,
    #     "type": "interactive",
    #     "interactive": {
    #         "type": "button",
    #         "body": {"text": body},
    #         "action": {
    #             "buttons": [
    #                 {
    #                     "type": "reply",
    #                     "reply": {
    #                         "id": f"paid_{payment_id}",
    #                         "title": "✅ Mark as Paid",
    #                     },
    #                 },
    #                 {
    #                     "type": "reply",
    #                     "reply": {
    #                         "id": f"snooze_{payment_id}",
    #                         "title": "📅 Remind later",
    #                     },
    #                 },
    #             ]
    #         },
    #     },
    # }

    # headers = {
    #     "Authorization": f"Bearer {settings.wa_access_token}",
    #     "Content-Type": "application/json",
    # }
    # print(f"DEBUG sending to phone: '{phone}'")
    # response = await client.post(url, json=payload, headers=headers)

    # if response.status_code >= 400:
    #     error_body = await response.aread()
    #     raise Exception(f"WhatsApp API error: {response.status_code} - {error_body.decode()}")

    # data = response.json()
    # return data["messages"][0]["id"]
    
    # test with simple text message alone as meta not sending interactive messages 
    client = _get_client()
    payment_id = payment["id"]
    description = payment["description"]
    category = payment.get("category", "Payment")
    amount = payment["amount"]
    due_date = _format_date(payment["due_date"])

    url = f"https://graph.facebook.com/v19.0/{settings.wa_phone_number_id}/messages"

    body = (
        f"Hi {first_name} 👋\n\n"
        f"*Payment Reminder*\n\n"
        f"📋 *{description}*\n"
        f"📂 Category: {category}\n"
        f"💰 Amount: ₹{amount:,.2f}\n"
        f"📅 Due: {due_date} ({days_label})\n\n"
        f"Reply *paid* if you have already paid\n"
        f"Reply *snooze* to set a custom reminder date"
    )

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": phone,
        "type": "text",
        "text": {"body": body},
    }

    headers = {
        "Authorization": f"Bearer {settings.wa_access_token}",
        "Content-Type": "application/json",
    }

    print(f"DEBUG sending to phone: '{phone}'")
    response = await client.post(url, json=payload, headers=headers)

    if response.status_code >= 400:
        raise Exception(f"WhatsApp API error: {response.status_code} - {response.text}")

    data = response.json()
    return data["messages"][0]["id"]


async def send_text(phone: str, text: str) -> str:
    """
    Send a plain text message.

    Args:
        phone: Phone number in international format without +
        text: Message text

    Returns:
        The WhatsApp message ID
    """
    client = _get_client()
    url = f"https://graph.facebook.com/v19.0/{settings.wa_phone_number_id}/messages"

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": phone,
        "type": "text",
        "text": {"body": text},
    }

    headers = {
        "Authorization": f"Bearer {settings.wa_access_token}",
        "Content-Type": "application/json",
    }

    response = await client.post(url, json=payload, headers=headers)

    if response.status_code >= 400:
        error_body = await response.aread()
        raise Exception(f"WhatsApp API error: {response.status_code} - {error_body.decode()}")

    data = response.json()
    return data["messages"][0]["id"]


async def ask_for_snooze_date(phone: str, payment_description: str) -> str:
    """
    Ask the user for a custom snooze date.

    Args:
        phone: Phone number in international format without +
        payment_description: Description of the payment being snoozed

    Returns:
        The WhatsApp message ID
    """
    text = (
        f"Sure! 📅 When would you like to be reminded about *{payment_description}*?\n\n"
        f"Please reply with a date in this format:\n"
        f"*DD-MM-YYYY*\n\n"
        f"Example: 25-06-2025"
    )
    return await send_text(phone, text)
