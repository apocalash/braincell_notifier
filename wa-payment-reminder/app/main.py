"""
Main FastAPI application entry point.
Handles startup/shutdown lifecycle and route registration.
"""
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from app.config import settings
from app.db import init_pool, close_pool
from app.queue import init_redis, close_redis, start_worker
from app.scheduler import create_scheduler, run_scheduler
from app.webhook import router as webhook_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application lifespan: startup and shutdown.
    """
    # STARTUP
    print("Starting up...")
    await init_pool()
    await init_redis()
    scheduler = create_scheduler()
    scheduler.start()
    asyncio.create_task(start_worker())
    print("Startup complete")
    yield
    # SHUTDOWN
    print("Shutting down...")
    scheduler.shutdown(wait=False)
    await close_redis()
    await close_pool()
    print("Shutdown complete")


app = FastAPI(
    title="WA Payment Reminder",
    version="1.0.0",
    description="WhatsApp Payment Reminder System using FastAPI",
    lifespan=lifespan,
)

# Include webhook router
app.include_router(webhook_router)


@app.get("/health")
async def health() -> dict:
    """
    Health check endpoint for Render and monitoring.
    """
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.post("/run-scheduler")
async def trigger_scheduler(request: Request) -> dict:
    """
    Manually trigger the scheduler (used by Render cron job).
    Requires x-cron-token header matching WA_WEBHOOK_VERIFY_TOKEN.
    """
    token = request.headers.get("x-cron-token", "")
    if token != settings.wa_webhook_verify_token:
        raise HTTPException(status_code=401, detail="Unauthorized")

    result = await run_scheduler()
    return {"success": True, **result}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.port,
        reload=False,
    )
