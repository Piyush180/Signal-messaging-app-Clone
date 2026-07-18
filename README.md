# Signal Clone — Real-Time Messaging

A full-stack, Signal-style messaging app: phone/OTP onboarding, contacts,
1-on-1 and group chats, real-time delivery with typing indicators, per-person
read receipts, presence, and a light/dark Signal-like UI.

- **Frontend:** Next.js 14 (App Router) + TypeScript
- **Backend:** FastAPI (async) + SQLAlchemy 2.0
- **Database:** SQLite (async via aiosqlite)
- **Real-time:** WebSockets

For the full reasoning behind every design decision, see
**[DESIGN.md](./DESIGN.md)**.

---

## Features

Core: mocked phone + OTP auth with session persistence; contacts (add by phone,
nickname, delete); conversation list sorted by recent activity with unread badges
and last-message preview; search; 1-on-1 real-time messaging with timestamps,
message status (sending → sent → delivered → read), typing indicators, and
online/last-seen presence; **reply-to / quoted messages** (WhatsApp-style, with
jump-to-original); group create, view members, and **admin add/remove members**;
all messages and group data persisted.

Signal-experience: conversation-list + chat-pane layout, message bubbles with
day separators and per-sender names in groups, modals for contacts/groups/
settings, toasts, a simulated encryption notice, and light/dark themes.

Placeholders (as the brief allows): voice/video calls, Stories, linked devices,
and real end-to-end encryption.

---

## Quick start

You need **Python 3.10+** and **Node.js 18+**.

### 1) Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # optional; sensible defaults work out of the box
uvicorn app.main:app --reload --port 8000
```

On first run the server creates the SQLite database and **seeds demo data**, so
the app is immediately usable. API docs are at http://127.0.0.1:8000/docs.

### 2) Frontend

```bash
cd frontend
npm install
cp .env.local.example .env.local   # points at http://127.0.0.1:8000 by default
npm run dev
```

Open http://localhost:3000.

### Demo accounts (OTP is always `123456`)

| Name | Phone |
| --- | --- |
| Alice Smith | `+15551234567` |
| Bob Jones | `+15559876543` |
| Charlie Brown | `+15555555555` |
| Diana Prince | `+15557778888` |

Log in as Alice in one browser and Bob in a private/incognito window to see
real-time messaging, typing, delivery, and read receipts between two people.

### Tests

```bash
cd backend
pytest          # auth flow, per-user unread/read receipts, pagination, group admin
```

---

## Architecture

```
Browser (Next.js)
   │  REST  (login, lists, history)        ┌───────────────────────────┐
   ├───────────────────────────────────────▶  FastAPI                  │
   │                                        │   api/  → services/       │
   │  WebSocket (live events)               │           │              │
   ╰───────────────────────────────────────▶  /ws  ────┘  manager (in- │
                                            │              memory socket│
                                            │              registry)    │
                                            │   models/ (SQLAlchemy)    │
                                            └──────────┬────────────────┘
                                                       ▼
                                                 SQLite (async)
```

Both the REST send endpoint and the WebSocket handler call the **same** message
service, so a message behaves identically no matter how it was sent. See
DESIGN.md §3 and §8.

---

## Database schema

Six tables: `users`, `otp_codes`, `contacts`, `conversations`,
`conversation_members`, `group_metadata`, `messages`.

Two design choices worth calling out (full explanation in DESIGN.md §4–5):

1. **One `conversations` table** for both direct and group chats (a direct chat
   is a conversation with two members and no name). This unifies messaging code.
2. **No `status` column on messages.** Delivery/read state is derived from two
   pointers on each membership row — `last_read_message_id` and
   `last_delivered_message_id` — which makes read receipts and unread counts
   correct *per person*, including in groups.

---

## API overview

REST base: `/api/v1`. All routes except the two auth routes require
`Authorization: Bearer <token>`.

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/auth/request-otp` | Issue a (mock) OTP |
| POST | `/auth/verify-otp` | Verify OTP, register if new, return JWT |
| GET | `/auth/me` | Current user |
| POST | `/auth/logout` | Client discards token |
| PUT | `/users/me` | Update profile |
| GET | `/users/search?q=` | Search users |
| GET/POST | `/contacts` | List / add contact |
| DELETE | `/contacts/{id}` | Remove contact |
| GET | `/conversations` | List conversations (recent first, unread counts) |
| POST | `/conversations/direct` | Get or create a 1-on-1 |
| POST | `/conversations/group` | Create a group |
| GET | `/conversations/{id}` | One conversation |
| POST | `/groups/{id}/members` | **Admin:** add members |
| DELETE | `/groups/{id}/members/{userId}` | **Admin:** remove a member |
| GET | `/conversations/{id}/messages?limit=&before_id=` | History (cursor-paginated) |
| POST | `/conversations/{id}/messages` | Send (REST fallback for the socket) |

WebSocket: `GET /ws?token=<jwt>`. Client → server: `ping`, `typing`,
`chat_message`, `read_receipt`. Server → client: `pong`, `new_message`,
`typing`, `presence`, `delivered`, `read_receipt`.

---

## Assumptions made

- Verification is mocked with a fixed OTP (`123456`), but the request → verify
  flow is enforced (you cannot verify without an issued code). Registration
  happens automatically on first successful verification.
- End-to-end encryption is simulated (a UI label), per the brief.
- Presence is best-effort from live socket connections; `last_seen` is recorded
  on disconnect. On server startup all users are reset to offline.
- The socket registry is in-memory, so the app runs as a single backend instance.
  DESIGN.md §11 describes the Redis Pub/Sub change needed to run multiple
  instances.
- SQLite is used as requested. The data layer is database-agnostic (SQLAlchemy),
  so PostgreSQL would work by changing `DATABASE_URL`.
- Deploy config is not committed because the assignment's hosted-demo step is
  environment-specific; the frontend reads its backend URL from
  `NEXT_PUBLIC_API_URL`, so pointing it at a deployed API is a one-line change.

---

## Project layout

```
backend/
  app/
    core/        config, database, security
    models/      SQLAlchemy tables
    schemas/     Pydantic request/response models
    services/    business logic (messages, conversations, presence)
    api/v1/      REST endpoints
    websockets/  socket endpoint + connection manager
    main.py      app entry + startup (create tables, seed)
    seed.py      demo data
  tests/         pytest suite
frontend/
  src/
    app/         App Router (layout, page, global styles)
    components/  Sidebar, ChatWindow, Avatar, modals
    context/     Auth + Socket providers
    lib/         api client, socket client, types, helpers
```
