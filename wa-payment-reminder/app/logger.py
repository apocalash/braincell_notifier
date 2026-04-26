"""
Message logging module.
Tracks all inbound and outbound WhatsApp messages.
"""
from app.db import execute


async def log_message(
    *,
    payment_id: int | None = None,
    user_id: int | None = None,
    direction: str,
    message: str,
    wa_msg_id: str | None = None,
) -> None:
    """
    Insert a row into message_log.
    Non-fatal — catches and logs all DB errors internally.

    Args:
        payment_id: The payment ID this message relates to (optional)
        user_id: The user ID this message relates to (optional)
        direction: "outbound" or "inbound"
        message: The message content
        wa_msg_id: The WhatsApp message ID (optional)
    """
    try:
        await execute(
            """
            INSERT INTO message_log (payment_id, user_id, direction, message, wa_msg_id)
            VALUES ($1, $2, $3, $4, $5)
            """,
            payment_id,
            user_id,
            direction,
            message,
            wa_msg_id,
        )
    except Exception as e:
        # Non-fatal: log to console but don't crash
        print(f"Failed to log message: {e}")
