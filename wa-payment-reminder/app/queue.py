"""
Redis queue module using redis.asyncio.
Provides job queue operations and conversation state management.
"""
import asyncio
import json
from typing import Optional, Any, Dict
import redis.asyncio as redis
from app.config import settings

# Module-level Redis client
_redis_client: Optional[redis.Redis] = None


async def init_redis() -> None:
    """Initialize the Redis client from Upstash URL."""
    global _redis_client
    _redis_client = redis.from_url(
        settings.upstash_redis_url,
        decode_responses=True,
    )
    print("Redis client initialized")


async def close_redis() -> None:
    """Close the Redis client gracefully."""
    global _redis_client
    if _redis_client:
        await _redis_client.close()
        _redis_client = None
        print("Redis client closed")


def get_redis() -> redis.Redis:
    """Get the current Redis client instance."""
    if _redis_client is None:
        raise RuntimeError("Redis client not initialized. Call init_redis() first.")
    return _redis_client


async def enqueue_reminder(job: Dict[str, Any]) -> None:
    """
    Add a reminder job to the queue.
    Job keys: payment_id, user_id, phone, user_name, description,
              amount, due_date, category, days_label
    """
    r = get_redis()
    await r.lpush("reminder_queue", json.dumps(job))


async def start_worker() -> None:
    """
    Background worker that processes the reminder queue.
    Runs indefinitely, polling for jobs.
    Rate limit: 10 messages/second (asyncio.sleep(0.1) between jobs).
    """
    from app.whatsapp import send_reminder
    from app.logger import log_message

    r = get_redis()
    print("Worker started, polling for jobs...")

    while True:
        try:
            # Block for 2 seconds waiting for a job
            result = await r.brpop("reminder_queue", timeout=2)

            if result:
                # result is a tuple: (queue_name, job_data)
                _, job_json = result
                job = json.loads(job_json)

                try:
                    # Send the reminder via WhatsApp
                    wa_msg_id = await send_reminder(
                        phone=job["phone"],
                        payment={
                            "id": job["payment_id"],
                            "description": job["description"],
                            "category": job["category"],
                            "amount": job["amount"],
                            "due_date": job["due_date"],
                        },
                        first_name=job["user_name"].split()[0] if " " in job["user_name"] else job["user_name"],
                        days_label=job["days_label"],
                    )

                    # Log the outbound message
                    await log_message(
                        payment_id=job["payment_id"],
                        user_id=job["user_id"],
                        direction="outbound",
                        message=f"Reminder: {job['description']} - Due {job['days_label']}",
                        wa_msg_id=wa_msg_id,
                    )

                    print(f"Sent reminder to {job['phone']} for payment {job['payment_id']}")

                except Exception as e:
                    print(f"Error sending reminder: {e}")
                    # Re-queue the job for retry (with a simple approach)
                    # In production, you might want exponential backoff
                    await r.rpush("reminder_queue_failed", job_json)

                # Rate limit: max 10 messages/second
                await asyncio.sleep(0.1)

        except Exception as e:
            print(f"Worker error: {e}")
            await asyncio.sleep(1)


# Conversation state management

async def set_user_state(phone: str, state: Dict[str, Any]) -> None:
    """
    Set conversation state for a user.
    TTL: 1 hour (3600 seconds).
    """
    r = get_redis()
    key = f"user_state:{phone}"
    await r.setex(key, 3600, json.dumps(state))


async def get_user_state(phone: str) -> Optional[Dict[str, Any]]:
    """
    Get conversation state for a user.
    Returns None if no state exists or expired.
    """
    r = get_redis()
    key = f"user_state:{phone}"
    value = await r.get(key)
    if value:
        return json.loads(value)
    return None


async def clear_user_state(phone: str) -> None:
    """Clear conversation state for a user."""
    r = get_redis()
    key = f"user_state:{phone}"
    await r.delete(key)
