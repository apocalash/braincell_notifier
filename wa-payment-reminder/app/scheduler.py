"""
Scheduler module using APScheduler.
Runs daily reminders at configured IST time.
"""
from datetime import date, datetime, timedelta
from typing import Any, Dict, List
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import pytz
from app.config import settings
from app.db import fetch, execute
from app.queue import enqueue_reminder


def get_days_label(days: int) -> str:
    """
    Generate a human-readable label for days until due.

    Args:
        days: Number of days until due (negative = overdue)

    Returns:
        Human-readable label
    """
    if days == 0:
        return "today"
    if days == 1:
        return "tomorrow"
    if days < 0:
        return f"{abs(days)} days overdue"
    return f"in {days} days"


async def run_scheduler() -> Dict[str, int]:
    """
    Daily scheduler job that finds payments due soon and queues reminders.

    Returns:
        Dict with total processed and queued counts
    """
    # Get today's date in IST
    ist = pytz.timezone("Asia/Kolkata")
    today = datetime.now(ist).date()

    # Calculate reminder window dates
    window_dates = [
        today + timedelta(days=30),  # 30 days out
        today + timedelta(days=7),   # 7 days out
        today + timedelta(days=1),   # 1 day out (tomorrow)
    ]

    # Find all payments that need reminders
    query = """
        SELECT
            p.id, p.description, p.category, p.amount, p.due_date, p.next_reminder_at,
            u.id AS user_id, u.name AS user_name, u.phone
        FROM payments p
        JOIN users u ON u.id = p.user_id
        WHERE u.is_active = TRUE
          AND p.status IN ('pending', 'snoozed')
          AND (
            p.due_date = ANY($1::date[])
            OR p.next_reminder_at = $2::date
          )
        ORDER BY p.due_date ASC
    """

    rows = await fetch(query, window_dates, today)

    processed = 0
    queued = 0

    for row in rows:
        processed += 1
        payment_id = row["id"]
        user_id = row["user_id"]
        phone = row["phone"]
        user_name = row["user_name"]
        description = row["description"]
        category = row["category"] or "Payment"
        amount = float(row["amount"])
        due_date = row["due_date"]
        next_reminder_at = row["next_reminder_at"]

        # Idempotency check: skip if already sent today
        idempotency_query = """
            SELECT 1 FROM message_log
            WHERE payment_id = $1
              AND direction = 'outbound'
              AND logged_at::date = $2::date
            LIMIT 1
        """
        existing = await fetch(idempotency_query, payment_id, today)
        if existing:
            print(f"Skipping payment {payment_id}: reminder already sent today")
            continue

        # Calculate days until due
        days_until = (due_date - today).days
        days_label = get_days_label(days_until)

        # Create job for queue
        job: Dict[str, Any] = {
            "payment_id": payment_id,
            "user_id": user_id,
            "phone": phone,
            "user_name": user_name,
            "description": description,
            "amount": amount,
            "due_date": due_date.isoformat(),
            "category": category,
            "days_label": days_label,
        }

        await enqueue_reminder(job)
        queued += 1

        # If this was a snoozed payment, reset to pending
        if next_reminder_at == today:
            await execute(
                "UPDATE payments SET status = 'pending', next_reminder_at = NULL WHERE id = $1",
                payment_id,
            )
            print(f"Reset snoozed payment {payment_id} to pending")

    print(f"Scheduler: processed {processed}, queued {queued} reminders")
    return {"processed": processed, "queued": queued}


def create_scheduler() -> AsyncIOScheduler:
    """
    Create and configure the APScheduler.

    Returns:
        Configured AsyncIOScheduler instance
    """
    ist = pytz.timezone("Asia/Kolkata")
    scheduler = AsyncIOScheduler(timezone=ist)

    scheduler.add_job(
        run_scheduler,
        trigger="cron",
        hour=settings.scheduler_hour,
        minute=settings.scheduler_minute,
        id="daily_reminder",
        replace_existing=True,
    )

    return scheduler
