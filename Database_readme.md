# Altiora AI — Database Schema (Phase 2)

## Quick Setup

```bash
# 1. Install PostgreSQL (if not installed)
# Windows: https://www.postgresql.org/download/windows/
# Or use Docker:
docker run --name altiora-db -e POSTGRES_PASSWORD=altiora_secret -e POSTGRES_DB=altiora -p 5432:5432 -d postgres:15

# 2. Connect to PostgreSQL
psql -h localhost -U postgres

# 3. Create the database
CREATE DATABASE altiora;
\c altiora

# 4. Run the migration
\i 001_schema.sql

# 5. Verify tables were created
\dt
```

## Entity Relationship Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                        ALTIORA AI - SCHEMA                          │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────┐    owns     ┌──────────────┐    has     ┌───────────┐ │
│  │  users   │────────────▶│  businesses   │──────────▶│ ai_agents │ │
│  └──────────┘             └──────────────┘            └───────────┘ │
│       │                     │    │    │                  │    │      │
│       │ member_of           │    │    │                  │    │      │
│       ▼                     │    │    │                  │    │      │
│  ┌──────────────┐           │    │    │         ┌───────┘    │      │
│  │business_     │◀──────────┘    │    │         │            │      │
│  │members       │                │    │         ▼            ▼      │
│  └──────────────┘                │    │  ┌───────────┐ ┌─────────┐ │
│                                  │    │  │  agent_   │ │ agent_  │  │
│  ┌──────────────┐                │    │  │ knowledge │ │ scripts │  │
│  │phone_numbers │◀───────────────┘    │  └───────────┘ └─────────┘ │
│  └──────────────┘                     │                             │
│                                       │                             │
│  ┌──────────┐    logs      ┌──────────▼──────┐                     │
│  │  calls   │◀─────────────│   (business)    │                     │
│  └──────────┘              └─────────────────┘                     │
│       │                         │         │                         │
│       │ transcript              │         │                         │
│       ▼                         ▼         ▼                         │
│  ┌──────────────┐    ┌──────────────┐  ┌──────────┐               │
│  │  call_       │    │subscriptions │  │ usage_   │                │
│  │  transcripts │    └──────────────┘  │ records  │                │
│  └──────────────┘                      └──────────┘                │
│                                                                      │
│  ┌──────────────┐    ┌──────────────┐  ┌──────────────────┐        │
│  │  api_keys    │    │webhook_events│  │subscription_plans│        │
│  └──────────────┘    └──────────────┘  └──────────────────┘        │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

## Tables Summary

| Table | Purpose | Key Relationships |
|---|---|---|
| `users` | Account owners & team members | → businesses, business_members |
| `businesses` | Tenants (companies using Altiora) | → users (owner), ai_agents, calls |
| `business_members` | Team access per business | → businesses, users |
| `phone_numbers` | Twilio numbers per business | → businesses, ai_agents |
| `ai_agents` | AI personality, voice, prompt config | → businesses |
| `agent_knowledge` | FAQ / knowledge base per agent | → ai_agents |
| `agent_scripts` | Call flow templates | → ai_agents |
| `calls` | Call logs (every call tracked) | → businesses, ai_agents |
| `call_transcripts` | Message-by-message transcript | → calls |
| `subscriptions` | Stripe billing per business | → businesses |
| `subscription_plans` | Available plans (Free→Enterprise) | standalone |
| `usage_records` | Monthly usage & cost tracking | → businesses |
| `webhook_events` | Stripe/Twilio event log | standalone |
| `api_keys` | External API access tokens | → businesses, users |

## Subscription Plans (Seeded)

| Plan | Price/mo | Minutes | Agents | Numbers |
|---|---|---|---|---|
| Free | $0 | 50 | 1 | 1 |
| Starter | $49 | 500 | 3 | 2 |
| Professional | $149 | 2,000 | 10 | 5 |
| Enterprise | $499 | 10,000 | 50 | 20 |

## Next Steps

After the schema is set up:
1. **Backend API** — FastAPI endpoints for CRUD on all tables
2. **Auth System** — JWT-based authentication with password hashing
3. **Next.js Dashboard** — Admin frontend consuming the API
4. **Stripe Integration** — Webhook handlers for billing events