# 🔔 WhatsApp Payment Reminder System

A production-ready backend service that automatically sends WhatsApp payment reminders and handles user replies via the Meta Cloud API.

---

## ✨ Features

- **Automated Reminders** — Sends WhatsApp reminders at 30 days, 7 days, and 1 day before payment due dates
- **Interactive Responses** — Users can tap buttons to mark as paid or request a custom snooze date
- **Conversation Flow** — Handles natural language replies with persistent state management
- **Idempotency** — Prevents duplicate reminders if both APScheduler and Render cron trigger on the same day
- **Timezone Aware** — All scheduling uses `Asia/Kolkata` (IST) timezone
- **Rate Limiting** — Worker limits message sending to 10 messages/second
- **Production Ready** — Deployable to Render with free tiers for all dependencies

---

## 🛠 Tech Stack

| Layer | Technology |
|---|---|
| Runtime | Python 3.11+ |
| Web Framework | FastAPI + Uvicorn |
| Database | PostgreSQL via asyncpg (Supabase) |
| Queue + State | Upstash Redis via redis.asyncio |
| Scheduler | APScheduler (AsyncIOScheduler) |
| WhatsApp | Meta Cloud API (REST via httpx) |
| Date Handling | python-dateutil + pytz |
| Config | pydantic-settings |

---

## 📁 Project Structure

```
braincell_notifier/
├── app/
│   ├── main.py          # FastAPI app entry point
│   ├── scheduler.py     # APScheduler setup and reminder jobs
│   ├── worker.py        # Queue consumer with rate limiting
│   ├── whatsapp.py      # Meta Cloud API client
│   ├── db.py            # PostgreSQL connection and queries
│   ├── redis_client.py  # Upstash Redis client and state helpers
│   └── config.py        # pydantic-settings config
├── requirements.txt
├── render.yaml          # Render deployment config
└── README.md
```

---

## 🚀 Getting Started

### Prerequisites

- Python 3.11+
- A [Supabase](https://supabase.com) project (PostgreSQL)
- An [Upstash](https://upstash.com) Redis database
- A [Meta Developer](https://developers.facebook.com) account with WhatsApp Cloud API access

### 1. Clone the repo

```bash
git clone https://github.com/apocalash/braincell_notifier.git
cd braincell_notifier
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Set up environment variables

Create a `.env` file in the root directory:

```env
# WhatsApp / Meta
WHATSAPP_TOKEN=your_meta_access_token
WHATSAPP_PHONE_NUMBER_ID=your_phone_number_id
VERIFY_TOKEN=your_webhook_verify_token

# PostgreSQL (Supabase)
DATABASE_URL=postgresql+asyncpg://user:password@host:port/dbname

# Redis (Upstash)
REDIS_URL=rediss://your_upstash_redis_url

# App
TIMEZONE=Asia/Kolkata
```

### 4. Run the server

```bash
uvicorn app.main:app --reload
```

---

## ⚙️ How It Works

### Reminder Schedule

The scheduler checks due dates daily and queues reminders at these intervals:

| Days Before Due | Reminder Type |
|---|---|
| 30 days | Early heads-up |
| 7 days | Follow-up reminder |
| 1 day | Final urgent reminder |

### User Interaction Flow

```
Bot sends reminder
       │
       ▼
User taps "Mark as Paid"  ──► Payment marked, conversation closed
       │
       or
       │
User taps "Snooze"        ──► Bot asks for custom date
       │
       ▼
User replies with date    ──► Reminder rescheduled
```

### Idempotency

Each reminder is keyed by `(user_id, due_date, reminder_type)` in Redis. If both APScheduler and the Render cron job fire on the same day, the second trigger is silently dropped.

---

## ☁️ Deploying to Render

This project is configured for deployment on [Render](https://render.com) using free-tier services.

1. Push your code to GitHub
2. Connect your repo to Render
3. Set all environment variables in the Render dashboard
4. Render will auto-deploy on every push to `master`

Alternatively, use the included `render.yaml` for infrastructure-as-code deployment.

---

## 📜 License

MIT License. See [LICENSE](LICENSE) for details.
