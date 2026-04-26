-- ============================================================
-- WhatsApp Payment Reminder System - Database Schema
-- Run this in Supabase SQL Editor to set up the database
-- ============================================================

-- Drop existing tables if needed (uncomment only if you want to reset)
-- DROP TABLE IF EXISTS message_log CASCADE;
-- DROP TABLE IF EXISTS payments CASCADE;
-- DROP TABLE IF EXISTS users CASCADE;

-- ============================================================
-- Users Table
-- Stores user information for payment reminders
-- ============================================================
CREATE TABLE IF NOT EXISTS users (
  id         SERIAL PRIMARY KEY,
  name       VARCHAR(100) NOT NULL,
  phone      VARCHAR(20) NOT NULL UNIQUE,  -- international format, no +: e.g. 919876543210
  is_active  BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- Payments Table
-- Stores payment due dates and reminder configuration
-- ============================================================
CREATE TABLE IF NOT EXISTS payments (
  id               SERIAL PRIMARY KEY,
  user_id          INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  description      VARCHAR(200) NOT NULL,
  category         VARCHAR(50),                        -- e.g. rent, utilities, loan, insurance
  amount           NUMERIC(12, 2) NOT NULL,
  due_date         DATE NOT NULL,
  status           VARCHAR(20) DEFAULT 'pending',      -- pending | paid | snoozed
  next_reminder_at DATE DEFAULT NULL,                  -- custom snooze date; NULL = use standard windows
  created_at       TIMESTAMPTZ DEFAULT NOW(),
  updated_at       TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- Message Log Table
-- Tracks all inbound and outbound WhatsApp messages
-- ============================================================
CREATE TABLE IF NOT EXISTS message_log (
  id         SERIAL PRIMARY KEY,
  payment_id INTEGER REFERENCES payments(id) ON DELETE SET NULL,
  user_id    INTEGER REFERENCES users(id) ON DELETE CASCADE,
  direction  VARCHAR(10) NOT NULL,   -- outbound | inbound
  message    TEXT,
  wa_msg_id  VARCHAR(100),
  logged_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- Indexes for Performance
-- ============================================================

-- Index for payment due date lookups (used by scheduler)
CREATE INDEX IF NOT EXISTS idx_payments_due_date ON payments(due_date);

-- Index for payment status filtering
CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(status);

-- Index for custom reminder date lookups
CREATE INDEX IF NOT EXISTS idx_payments_next_reminder_at ON payments(next_reminder_at);

-- Index for message log user lookups
CREATE INDEX IF NOT EXISTS idx_message_log_user_id ON message_log(user_id);

-- Index for message log date-based queries (idempotency checks)
CREATE INDEX IF NOT EXISTS idx_message_log_logged_at ON message_log(logged_at);

-- ============================================================
-- Trigger Function: Auto-update updated_at
-- ============================================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply trigger to payments table
CREATE TRIGGER IF NOT EXISTS update_payments_updated_at
    BEFORE UPDATE ON payments
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
    
-- ============================================================
-- Sample Data (Optional - Uncomment to insert sample users)
-- ============================================================

-- Sample user insert (uncomment and modify as needed):
-- INSERT INTO users (name, phone) VALUES
--   ('Arjun Mehta',       '919876543210'),
--   ('Priya Sharma',      '919876543211'),
--   ('Rohan Verma',       '919876543212'),
--   ('Sneha Pillai',      '919876543213'),
--   ('Karthik Nair',      '919876543214'),
--   ('Divya Iyer',        '919876543215'),
--   ('Rahul Gupta',       '919876543216'),
--   ('Ananya Bose',       '919876543217'),
--   ('Vikram Patel',      '919876543218'),
--   ('Meena Krishnan',    '919876543219')
-- ON CONFLICT (phone) DO NOTHING;

-- Sample payment insert (uncomment after inserting users):
-- INSERT INTO payments (user_id, description, category, amount, due_date) VALUES
--   (1,  'Monthly Rent',           'rent',       28000.00, '2025-06-01'),
--   (1,  'Electricity Bill',       'utilities',   1450.75, '2025-06-18'),
--   (1,  'LIC Premium',            'insurance',   4200.00, '2025-06-25'),
--   (2,  'Home Loan EMI',          'loan',       42000.00, '2025-06-05'),
--   (2,  'Water Bill',             'utilities',    380.00, '2025-06-12'),
--   (2,  'Car Insurance',          'insurance',   9500.00, '2025-06-28'),
--   (3,  'Monthly Rent',           'rent',       18500.00, '2025-06-01'),
--   (3,  'Personal Loan EMI',      'loan',       12000.00, '2025-06-08'),
--   (3,  'Internet Bill',          'utilities',    999.00, '2025-06-15'),
--   (4,  'Home Loan EMI',          'loan',       55000.00, '2025-06-05'),
--   (4,  'Electricity Bill',       'utilities',   2100.00, '2025-06-20'),
--   (4,  'Health Insurance',       'insurance',   6800.00, '2025-06-30'),
--   (5,  'Monthly Rent',           'rent',       22000.00, '2025-06-01'),
--   (5,  'Gas Bill',               'utilities',    650.00, '2025-06-14'),
--   (5,  'Two-Wheeler Loan EMI',   'loan',        4500.00, '2025-06-10'),
--   (6,  'Flat Maintenance',       'rent',        3500.00, '2025-06-07'),
--   (6,  'Broadband Bill',         'utilities',   1199.00, '2025-06-17'),
--   (6,  'Term Insurance',         'insurance',   8200.00, '2025-06-22'),
--   (7,  'Monthly Rent',           'rent',       32000.00, '2025-06-01'),
--   (7,  'Electricity Bill',       'utilities',   1875.50, '2025-06-19'),
--   (7,  'Car Loan EMI',           'loan',       18000.00, '2025-06-06'),
--   (7,  'Health Insurance',       'insurance',   5500.00, '2025-06-25'),
--   (8,  'Home Loan EMI',          'loan',       38000.00, '2025-06-05'),
--   (8,  'Electricity Bill',       'utilities',    920.00, '2025-06-16'),
--   (8,  'Mobile Postpaid',        'utilities',    799.00, '2025-06-21'),
--   (9,  'Monthly Rent',           'rent',       15000.00, '2025-06-01'),
--   (9,  'Personal Loan EMI',      'loan',        9500.00, '2025-06-09'),
--   (9,  'Vehicle Insurance',      'insurance',   7100.00, '2025-06-27'),
--   (10, 'Society Maintenance',    'rent',        4200.00, '2025-06-07'),
--   (10, 'Electricity Bill',       'utilities',   1600.00, '2025-06-18'),
--   (10, 'Home Loan EMI',          'loan',       61000.00, '2025-06-05'),
--   (10, 'Life Insurance Premium', 'insurance',  11500.00, '2025-06-23')
-- ON CONFLICT DO NOTHING;

-- ============================================================
-- Schema Verification Query (Run to verify setup)
-- ============================================================
-- SELECT
--     (SELECT COUNT(*) FROM users) as user_count,
--     (SELECT COUNT(*) FROM payments) as payment_count,
--     (SELECT COUNT(*) FROM message_log) as log_count;