# WhatsApp Payment Reminder System

A production-ready backend service that automatically sends WhatsApp payment reminders and handles user replies.

## Features

- **Automated Reminders**: Sends WhatsApp reminders at 30 days, 7 days, and 1 day before payment due dates
- **Interactive Responses**: Users can tap buttons to mark as paid or request a custom snooze date
- **Conversation Flow**: Handles natural language replies with state management
- **Idempotency**: Prevents duplicate reminders if both APScheduler and Render cron trigger on the same day
- **Timezone Aware**: All scheduling uses Asia/Kolkata (IST) timezone
- **Rate Limiting**: Worker limits message sending to 10 messages/second
- **Production Ready**: Deployable to Render with free tiers for all dependencies

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Runtime | Python 3.11+ |
| Web Framework | FastAPI + Uvicorn |
| Database | PostgreSQL via asyncpg (Supabase) |
| Queue + State | Upstash Redis via redis.asyncio |
| Scheduler | APScheduler (AsyncIOScheduler) |
| WhatsApp | Meta Cloud API (REST via httpx) |
| Date Handling | python-dateutil + pytz |
| Config | pydantic-settings |

## Prerequisites

- Python 3.11 or higher
- Git
- Accounts on:
  - [Supabase](https://supabase.com) (free PostgreSQL)
  - [Meta for Developers](https://developers.facebook.com) (WhatsApp API)
  - [Upstash](https://upstash.com) (free Redis)
  - [Render](https://render.com) (free hosting)
  - [GitHub](https://github.com) (code repository)

## Quick Start

### Step 1: Clone & Setup Environment

```bash
git clone https://github.com/YOUR_USERNAME/wa-payment-reminder.git
cd wa-payment-reminder
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your actual values
```

### Step 2: Supabase Setup

1. Create a new project at [supabase.com](https://supabase.com)
2. Go to **SQL Editor** → **New query**
3. Copy and paste the contents of `config/migrate.sql`
4. Click **Run**
5. Go to **Settings** → **Database** → **Connection string (URI mode)**
6. Copy the connection string and paste it as `DATABASE_URL` in your `.env` file

### Step 3: Meta Cloud API Setup

1. Go to [developers.facebook.com](https://developers.facebook.com)
2. Create a new app → Select **Business** type
3. Add **WhatsApp** product to your app
4. Go to **API Setup**:
   - Copy **Phone Number ID** → set as `WA_PHONE_NUMBER_ID`
   - Generate a permanent **System User Token** → set as `WA_ACCESS_TOKEN`
5. Set `WA_WEBHOOK_VERIFY_TOKEN` to any random secret string (you choose this)
6. Add a test phone number and verify it with the WhatsApp code

### Step 4: Upstash Redis Setup

1. Go to [console.upstash.com](https://console.upstash.com)
2. Create a new **Redis** database (free tier)
3. Copy the `rediss://` URL → paste as `UPSTASH_REDIS_URL` in your `.env`
4. Make sure the database is in the same region as your Render deployment

### Step 5: Run Locally

```bash
# Activate virtual environment
source venv/bin/activate

# Start the server
python app/main.py
```

Test the health endpoint:
```bash
curl http://localhost:8000/health
```

Test webhook verification:
```bash
curl "http://localhost:8000/webhook?hub.mode=subscribe&hub.verify_token=YOUR_VERIFY_TOKEN&hub.challenge=test123"
# Expected response: test123
```

Manually trigger the scheduler:
```bash
curl -X POST http://localhost:8000/run-scheduler \
  -H "x-cron-token: YOUR_VERIFY_TOKEN"
```

### Step 6: Push to GitHub

```bash
git init
git add .
git commit -m "Initial commit: WA payment reminder"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/wa-payment-reminder.git
git push -u origin main
```

### Step 7: Deploy on Render

1. Go to [render.com](https://render.com)
2. Click **New** → **Blueprint**
3. Connect your GitHub repository
4. Render reads `render.yaml` and creates:
   - Web service (wa-payment-reminder)
   - Cron job (wa-payment-reminder-cron)
5. Go to each service → **Environment** tab → add all required env vars
6. The web service will deploy automatically

### Step 8: Register Webhook with Meta

1. Go to Meta Developer Console → **WhatsApp** → **Configuration**
2. Click **Edit** next to **Webhook**
3. Set **Callback URL**: `https://your-app-name.onrender.com/webhook`
4. Set **Verify token**: same as `WA_WEBHOOK_VERIFY_TOKEN`
5. Click **Verify and save**
6. Under **Webhook Fields**, subscribe to `messages`

### Step 9: Keep Render Awake (Optional)

Render free tier spins down after 15 minutes of inactivity.

1. Go to [uptimerobot.com](https://uptimerobot.com)
2. Create a new **HTTP(s)** monitor
3. Set URL: `https://your-app-name.onrender.com/health`
4. Set interval: 5 minutes
5. This pings your app every 5 minutes to keep it awake

## Database Schema

### Users Table
```sql
CREATE TABLE users (
  id         SERIAL PRIMARY KEY,
  name       VARCHAR(100) NOT NULL,
  phone      VARCHAR(20) NOT NULL UNIQUE,  -- e.g., 919876543210
  is_active  BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### Payments Table
```sql
CREATE TABLE payments (
  id               SERIAL PRIMARY KEY,
  user_id          INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  description      VARCHAR(200) NOT NULL,
  category         VARCHAR(50),  -- rent, utilities, loan, insurance
  amount           NUMERIC(12, 2) NOT NULL,
  due_date         DATE NOT NULL,
  status           VARCHAR(20) DEFAULT 'pending',  -- pending | paid | snoozed
  next_reminder_at DATE DEFAULT NULL,  -- custom snooze date
  created_at       TIMESTAMPTZ DEFAULT NOW(),
  updated_at       TIMESTAMPTZ DEFAULT NOW()
);
```

### Message Log Table
```sql
CREATE TABLE message_log (
  id         SERIAL PRIMARY KEY,
  payment_id INTEGER REFERENCES payments(id) ON DELETE SET NULL,
  user_id    INTEGER REFERENCES users(id) ON DELETE CASCADE,
  direction  VARCHAR(10) NOT NULL,  -- outbound | inbound
  message    TEXT,
  wa_msg_id  VARCHAR(100),
  logged_at  TIMESTAMPTZ DEFAULT NOW()
);
```

## Adding Payment Data

Insert sample users:
```sql
INSERT INTO users (name, phone) VALUES
  ('John Doe', '919876543210'),
  ('Jane Smith', '919876543211')
ON CONFLICT (phone) DO NOTHING;
```

Insert sample payments:
```sql
INSERT INTO payments (user_id, description, category, amount, due_date) VALUES
  (1, 'Monthly Rent', 'rent', 25000.00, '2025-06-15'),
  (1, 'Electricity Bill', 'utilities', 1250.50, '2025-06-20'),
  (2, 'Car Insurance', 'insurance', 8500.00, '2025-06-25')
ON CONFLICT DO NOTHING;
```

## Message Flow

```
APScheduler (8 AM IST)
     │
     ▼
run_scheduler() — queries DB for due payments
     │
     ▼ enqueue_reminder()
Redis Queue ("reminder_queue")
     │
     ▼ start_worker() polls continuously
send_reminder() — Meta Cloud API
     │
     ▼
User's WhatsApp ──── taps button / types reply ────┐
                                                    │
                                      POST /webhook ▼
                                   handle_inbound_message()
                                                    │
                           ┌────────────────────────┤
                           ▼                        ▼
                    mark_as_paid()         handle_snooze_date()
                           │                        │
                           └──────────┬─────────────┘
                                      ▼
                              UPDATE payments (DB)
                              log_message (DB)
                              send_text confirmation
```

## Project Structure

```
wa-payment-reminder/
├── app/
│   ├── main.py           # FastAPI app factory, lifespan, route registration
│   ├── config.py         # pydantic-settings Settings class
│   ├── db.py             # asyncpg pool init, execute(), fetch(), fetchrow()
│   ├── scheduler.py      # APScheduler setup, run_scheduler() job function
│   ├── queue.py          # Redis queue: enqueue, worker loop, user state
│   ├── whatsapp.py       # Meta Cloud API client
│   ├── webhook.py        # FastAPI router: GET/POST /webhook
│   ├── logger.py         # log_message(): writes to message_log table
│   └── date_parser.py    # parse_user_date(): parses DD-MM-YYYY / DD/MM/YYYY
├── config/
│   └── migrate.sql       # Full DB schema
├── .env.example          # All required env vars with comments
├── .gitignore            # __pycache__, .env, venv/, etc.
├── requirements.txt      # All pinned dependencies
├── render.yaml           # Render Blueprint: web service + cron job
└── README.md             # This file
```

## Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `DATABASE_URL` | Supabase PostgreSQL connection string | `postgresql://...` |
| `WA_PHONE_NUMBER_ID` | Meta WhatsApp Phone Number ID | `123456789012345` |
| `WA_ACCESS_TOKEN` | Meta permanent System User Token | `EAA...` |
| `WA_WEBHOOK_VERIFY_TOKEN` | Random secret for webhook verification | `my_secret_123` |
| `UPSTASH_REDIS_URL` | Upstash Redis connection URL | `rediss://...` |
| `PORT` | Server port (Render sets this) | `8000` |
| `APP_ENV` | Environment name | `development` or `production` |
| `APP_BASE_URL` | Base URL for cron job callbacks | `https://...onrender.com` |
| `SCHEDULER_HOUR` | Hour in IST for daily reminders | `8` |
| `SCHEDULER_MINUTE` | Minute in IST for daily reminders | `0` |

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check endpoint |
| `/webhook` | GET | Meta webhook verification |
| `/webhook` | POST | Receive inbound messages from Meta |
| `/run-scheduler` | POST | Manually trigger scheduler (requires `x-cron-token` header) |

## User Interactions

**Reminder Message** shows two buttons:
- ✅ **Mark as Paid** — Instantly marks the payment as completed
- 📅 **Remind me later** — Asks for a custom date to be reminded

**Text Replies** accepted:
- `paid` — Marks the most recent pending payment as paid
- Any date in format `DD-MM-YYYY` — Sets a custom reminder date

## Security & Edge Cases

- **Idempotency**: Duplicate reminders are prevented by checking message_log
- **FastAPI 200-first rule**: Webhooks return 200 immediately, processing happens in background
- **Rate limiting**: Worker sleeps 0.1s between messages (max 10 msg/sec)
- **Conversation state TTL**: Redis keys expire after 1 hour
- **Timezone**: All dates use Asia/Kolkata (IST)
- **Phone format**: Stored without `+` prefix
- **Graceful errors**: All async operations wrapped in try/except
- **SSL required**: asyncpg uses SSL for Supabase connections

## License

MIT

## Troubleshooting

**ImportError: No module named 'app'**
- Make sure you're running from the project root directory
- Use `python -m app.main` instead of `python app/main.py`

**SSL errors with Supabase**
- Check that `ssl="require"` is set in db.py
- Verify your DATABASE_URL is correct

**Redis connection errors**
- Ensure you're using `rediss://` (with `s` for SSL) from Upstash
- Check that the Redis database is active

**Webhook verification fails**
- Verify `WA_WEBHOOK_VERIFY_TOKEN` matches between .env and Meta dashboard
- Check that the callback URL is correct and publicly accessible

**Messages not sending**
- Verify `WA_ACCESS_TOKEN` is a permanent System User Token, not a temporary one
- Check that your test phone number is verified in Meta dashboard
- Review Meta app dashboard for any policy violations
