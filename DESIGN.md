# Design Document — Signal Clone

This document explains **what** was built, **how** it works, and most importantly
**why** each decision was made. It is written to be read top-to-bottom by someone
from the ground up, so concepts are introduced before they are used. If you only read one file to understand the project, read this one.

Table of contents:

1. The big picture
2. Why this tech stack
3. Backend, explained from scratch (FastAPI + async + SQLAlchemy)
4. The database schema and the reasoning behind every table
5. The hardest part: message status, read receipts, and unread counts
6. Real-time: how WebSockets work here
7. Frontend, explained from scratch (Next.js App Router + TypeScript)
8. How a single message travels end-to-end
9. Security notes and honest tradeoffs
10. What is intentionally mocked or left out, and how I'd extend it
11. Scaling: what breaks first and what I'd change

---

## 1. The big picture

The app is split into two programs that talk over the network:

- a **backend** (Python, FastAPI) that owns the database and all the rules,
- a **frontend** (Next.js, TypeScript) that runs in the browser and draws the UI.

They communicate two ways:

- **HTTP REST** for request/response actions ("log me in", "list my chats",
  "load older messages"). The browser asks, the server answers, done.
- **WebSocket** for real-time events ("a new message arrived", "X is typing",
  "Y came online"). This is a connection that stays open so the server can
  *push* to the browser without being asked.

A useful mental model: REST is like sending letters, WebSocket is like keeping a
phone line open. You use letters for "send me my history" and the open line for
"tell me the instant something happens".

---

## 2. Why this tech stack

The assignment asked for **Next.js (TypeScript)** on the frontend and
**Python (FastAPI/Django)** on the backend, with **SQLite** and a real-time
mechanism. Here is the reasoning behind the specific choices inside those bounds.

**FastAPI over Django.** FastAPI is async-first, which matters for a chat app:
a WebSocket server spends almost all its time *waiting* (for the next message,
the next event). Async lets one process wait on thousands of idle connections
cheaply. Django's async support exists but its ecosystem is still mostly
synchronous, so FastAPI is the more natural fit here. FastAPI also gives you
automatic request validation (via Pydantic) and interactive API docs for free.

**SQLite.** The brief says SQLite and "design your own schema". SQLite needs
zero setup — the database is a single file — so a reviewer can clone and run
with no database server to install. The data-access code uses SQLAlchemy, so the
same code would run on PostgreSQL by changing one connection string; nothing in
the app depends on SQLite-specific behaviour.

**Next.js App Router + TypeScript.** Next.js is the requested framework.
TypeScript adds static types, which catch a whole class of bugs before the code
ever runs (e.g. "this message might not have a sender" becomes a compile error,
not a crash). See section 7 for how the App Router is actually used here.

**Plain CSS with design tokens** instead of a UI library. The look is driven by
a small set of CSS variables (`--signal-blue`, `--bg-panel`, …) defined once and
swapped for dark mode. This keeps the bundle small and the styling easy to
explain, and it makes the light/dark themes provably consistent because they
share the same variable names.

---

## 3. Backend, explained from scratch

### 3.1 What "async" means here

Python functions defined with `async def` can *pause* at an `await` and let the
program do other work while waiting for I/O (a database read, a network send).
FastAPI runs these on an event loop. You do not manage threads; you just mark the
slow, waiting parts with `await`. Every database call in this project is awaited,
so a single worker can serve many users without blocking.

### 3.2 Layers, and why they exist

The backend is organised so each file has one job:

```
app/
  core/        config, database engine, security (JWT, OTP)
  models/      SQLAlchemy ORM tables (the shape of the data)
  schemas/     Pydantic models (the shape of the JSON in/out of the API)
  services/    business logic (the rules) — no HTTP here
  api/         thin HTTP endpoints that call services
  websockets/  the socket endpoint + the connection registry
```

Why separate **models**, **schemas**, and **services**?

- **Models** describe how data is stored in the database.
- **Schemas** describe how data looks on the wire (the API contract). Keeping
  these separate means you can change a column without automatically leaking it
  to clients, and you can validate input precisely.
- **Services** hold the actual rules ("only an admin can remove a member",
  "a message updates everyone's delivery pointer"). Endpoints stay tiny — they
  parse the request, call a service, return the result. The huge benefit: the
  REST endpoint and the WebSocket handler both call the *same* service to send a
  message, so a message behaves identically no matter how it arrived.
  Duplicating that logic per transport is exactly how the two paths drift apart
  (an HTTP send that persists but forgets to broadcast, say). One service, one
  behaviour.

### 3.3 Sessions and the `get_db` dependency

A database **session** is one unit of work. `get_db` (in `core/database.py`)
hands each HTTP request its own session and guarantees it is closed afterwards,
using FastAPI's dependency system:

```python
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
```

Endpoints declare `db: AsyncSession = Depends(get_db)` and never worry about
opening or closing connections. WebSockets are different — they live for minutes,
not milliseconds — so the socket handler opens a *short* session per event
instead of holding one open the whole time.

### 3.4 Authentication (mocked, but shaped like the real thing)

The flow is: `POST /auth/request-otp` stores a one-time code and returns it (only
because this is a demo); `POST /auth/verify-otp` checks the code and, if the
phone number is new, **registers** the user, then returns a **JWT**.

A JWT (JSON Web Token) is a signed string that says "this is user #5" and cannot
be tampered with because the server signs it with a secret key. The client sends
it on every request in the `Authorization: Bearer <token>` header. The server
verifies the signature and loads the user — no session storage needed on the
server side, which is what "stateless auth" means.

One deliberate choice: verify-otp **requires** a real, unexpired, unused OTP
row. The lazier mock — accepting the fixed code `123456` for any number even
with no OTP issued — would make the entire OTP table meaningless. The code is
still mocked (always `123456`), but the *flow* is enforced, so swapping in a
real SMS provider is a one-function change.

---

## 4. The database schema

Six tables. Here is each one and the reasoning.

**users** — one row per person. Holds profile fields plus presence
(`is_online`, `last_seen`).

**otp_codes** — issued verification codes with an expiry and a used-flag.

**contacts** — a *directional* "A saved B" row with an optional nickname.
Directional because you saving me does not mean I saved you. A unique constraint
on `(user_id, contact_user_id)` stops duplicates.

**conversations** — the key design decision. There is **one** table for both
1-on-1 and group chats, distinguished by a `type` column. A direct chat is just a
conversation with exactly two members and no name. Why unify them? Because
messages, membership, unread counts, and read receipts then have **one** code
path instead of two parallel ones. Fewer paths means fewer bugs and half the code.

**conversation_members** — the junction table linking users to conversations,
with a `role` (`admin`/`member`) and two pointers that are the heart of the app:
`last_read_message_id` and `last_delivered_message_id`. Section 5 explains these.
A unique constraint on `(conversation_id, user_id)` prevents joining twice.

**group_metadata** — name, description, avatar, and creator for a group
(one row per group conversation).

**messages** — one row per message. Columns: who sent it, the conversation, the
text, a `message_type` (`text` or `system`), and a timestamp. Note what is
**not** here: there is no `status` column. That absence is the single most
important schema decision, explained next.

A composite index on `messages(conversation_id, id)` makes the hot query — "the
newest N messages in this conversation" — a fast range scan instead of a full
table scan.

### Consistent timestamps

Every timestamp in the system is created the same way: in Python, as a
timezone-aware UTC value (`utcnow()` in `models/common.py`). Mixing the
database clock (`func.now()`, which SQLite stores as a naive string) with the
app clock (`datetime.now(timezone.utc)`, an offset-aware string) puts two
formats in one column, which breaks sorting and forces the frontend to guess
which timestamps carry a "Z". Pick one clock and one format everywhere — the
whole bug class disappears.

---

## 5. The hardest part: status, read receipts, unread counts

This is the easiest part of a chat app to get subtly wrong, so it is worth
the detail.

**The wrong model (naive):** a single `status` string on each message
(`sent`/`delivered`/`read`). That can only describe **one** reader. In a group of
five, when one person reads a message, flipping its status to "read" wrongly
claims everyone read it. Unread counts had the same flaw — they were global to
the message, not per person.

**The right model (here):** status is not stored on the message. Instead, each
membership row carries two pointers:

- `last_read_message_id` — the highest message id this member has read,
- `last_delivered_message_id` — the highest id delivered to a live socket.

From these two numbers per member, everything is *derived*:

- **Unread count for me** = number of messages in the conversation with
  `id > my last_read_message_id` that I did not send. Per person, automatically.
- **A message's status, shown to its sender** = look at the *other* members'
  pointers and take the weakest: `read` if every other member has read up to it,
  else `delivered` if every other member has at least received it, else `sent`.
  In a 1-on-1 chat "every other member" is just one person, so you get the exact
  single-tick / double-tick / blue-double-tick behaviour. In a group it correctly
  means "read by everyone".

This is the same idea Signal and WhatsApp use. Storing a pointer per member is
cheap (two integers) and makes the correct behaviour fall out of simple
comparisons. The code lives in `services/messages.py` (`_status_for`,
`unread_count`, `mark_read`).

There is also a fourth, client-only status: **`sending`**. When you hit send, the
UI shows the bubble immediately with a clock icon before the server has confirmed
it (this is "optimistic UI"). When the server echoes the saved message back, the
bubble upgrades to `sent`/`delivered`. Without this state your message would
not appear until the server round-tripped — which feels laggy and, worse,
silently loses the message if the send fails.

### 5.5 Reply-to / quoted messages

Replies are a real relation, not decorated text. `messages.reply_to_id` is a
nullable self-referencing foreign key with `ON DELETE SET NULL`, so deleting a
quoted message degrades a reply into a normal message instead of cascading.

Three decisions worth defending:

- **Server-side validation.** The quoted id must exist *and* belong to the same
  conversation. Trusting the client here would let a crafted request quote a
  message from a chat the sender cannot even see — a small information leak.
  Both transports (REST and WebSocket) hit the same check in the service.
- **A compact `QuotedMessage` preview** (id, sender, content) is embedded in the
  response instead of nesting a full recursive `MessageResponse`. Quotes never
  need receipts or their own quotes, and a flat shape keeps serialization
  cheap. History eager-loads the quote and its sender (`selectinload`) so a
  50-message page stays at a fixed number of queries.
- **Optimistic replies.** The composer keeps the pending quote locally, so the
  reply bubble renders complete (quote included) the instant you hit send, then
  reconciles with the server echo by `client_id` like any other message.
  Clicking a quote scrolls to and briefly highlights the original, if loaded.

---

## 6. Real-time with WebSockets

### 6.1 The connection registry

`websockets/manager.py` keeps an in-memory dictionary: `user_id -> set of open
sockets` (a set, because you might have two tabs open). It can send a payload to
every socket of a user and report whether a user is online. It knows nothing
about the database — that separation is what lets both REST and WebSocket code
call the same broadcast helper.

### 6.2 The event loop

`websockets/endpoints.py` is the single `/ws` endpoint. On connect it
authenticates the token, registers the socket, marks the user online, and marks
pending messages delivered. Then it loops, reading JSON events:

- `ping` → replies `pong` (heartbeat, so a dead link is noticed),
- `typing` → tells the other members,
- `chat_message` → calls the message service to persist + broadcast,
- `read_receipt` → marks the conversation read and notifies senders.

The critical robustness detail: the receive loop is wrapped so that **any**
exception — including a malformed frame — still runs cleanup in a `finally`
block. Catching only the normal disconnect is a classic leak: any other error
skips cleanup and leaves the user stuck "online" forever. Cleanup must never
depend on the happy path.

On startup the server also resets everyone to offline, so a crash can't leave
stale "online" flags in the database.

### 6.3 Why the frontend socket reconnects

A raw browser WebSocket does not reconnect itself. If the Wi-Fi blips or the
server restarts, it closes and stays closed — and the app silently stops
receiving messages until a full page reload. The `ReconnectingSocket` class
(`lib/ws.ts`) handles this with three behaviours: automatic reconnect with
**exponential backoff** (0.5s, 1s, 2s, … capped, so a downed server isn't
hammered), a periodic **heartbeat ping**, and re-authentication on every
reconnect. The UI shows a "Reconnecting…" banner while it's down.

---

## 7. Frontend, explained from scratch

### 7.1 Next.js App Router in one paragraph

Next.js lets a component render on the **server** (a "Server Component",
the default) or in the **browser** (a "Client Component", opted in with
`"use client"` at the top of the file). Server Components are great for content
you can render before sending HTML — a blog, a product page — because the user
sees content instantly and ships less JavaScript. Client Components are for
anything interactive: state, effects, event handlers, browser APIs.

### 7.2 Why this app is client-driven (an honest tradeoff)

A chat app is almost entirely interactive and personal: it needs the logged-in
user, a live socket, local state for typing/optimistic messages, and it has no
meaningful content to show a logged-out visitor. So the main page
(`app/page.tsx`) is a Client Component. The App Router still earns its keep here:
it gives us the file-based routing, the shared `layout.tsx`, the pre-hydration
theme script (no flash of the wrong theme), and a clean path to add real Server
Components later (e.g. a marketing landing page or SEO pages) without changing
the chat. The point of learning: "use the framework's default (server) unless the
work is inherently client-side — and be able to say *why* you opted out." Here
the why is real-time interactivity and per-user state.

### 7.3 State, contexts, and the single subscription

Two React Contexts wrap the app:

- `AuthContext` — who is logged in; restores the session on load by calling
  `/me`; exposes `login`/`logout`.
- `SocketContext` — owns the one WebSocket, exposes typed `sendChat`,
  `sendTyping`, `sendRead`, and a `subscribe(handler)` function.

Components **subscribe** to socket events rather than reading a single
"last event" value. Why: if two events arrive in the same tick, a single shared
value would overwrite the first before a listener saw it. A subscription set
delivers every event to every current listener. `page.tsx` registers exactly one
subscription and uses refs (`activeIdRef`, `userRef`) so that long-lived handler
always sees the latest state without re-subscribing on every keystroke.

### 7.4 The typed API client

`lib/api.ts` is the only place that talks HTTP. Every call attaches the token,
sets a 15-second timeout, and converts a non-2xx response into a thrown `Error`
carrying the server's message. On a genuine `401` it clears the token and fires
an event that logs the UI out — but *only* on a real 401. Treating a timeout
as an auth failure would let a slow network delete a perfectly valid token and
sign you out; the two failure modes are kept strictly separate.

---

## 8. How one message travels end-to-end

1. You type and hit send. `page.tsx` creates an **optimistic** message with a
   temporary id and a `client_id`, shows it immediately with a clock icon, and
   calls `sendChat` over the socket.
2. The server's socket handler validates membership and calls
   `messages.create_and_broadcast`.
3. That service, in **one transaction**: inserts the row, bumps the
   conversation's `updated_at`, sets the sender's read+delivered pointers to this
   message, and sets `delivered` for any recipient currently online.
4. It then pushes a `new_message` event to every member's sockets. Each recipient
   receives it and appends it; the sender receives it and **replaces** the
   optimistic bubble (matched by `client_id`), upgrading the clock to a tick.
5. When a recipient has the chat open, the client sends `read_receipt`. The
   server advances that member's `last_read_message_id` and broadcasts
   `read_receipt`; the sender's ticks turn blue.

If the socket is down at step 1, the client falls back to `POST …/messages`,
which calls the *same* service — so the message is still persisted, still bumps
the conversation, and still broadcasts to everyone else.

---

## 9. Security notes and honest tradeoffs

- **Token storage.** The token is kept in `localStorage`. This is simple and
  works across the REST client and the WebSocket URL. The tradeoff: `localStorage`
  is readable by JavaScript, so a cross-site-scripting (XSS) bug could steal it.
  The more secure alternative is an `httpOnly` cookie the browser sends
  automatically and JS cannot read — but that needs CSRF protection and makes the
  cross-origin WebSocket handshake fiddlier. For a demo I chose clarity and made
  the tradeoff explicit; a production build should move to `httpOnly` cookies.
- **CORS.** The API allows a specific list of origins from config. It never
  uses `"*"` together with credentials, because browsers forbid that exact
  combination and the credentialed path would silently fail cross-origin.
- **Secrets.** `SECRET_KEY` has an obviously-a-dev default and is meant to be
  overridden by an environment variable in production. Nothing sensitive is
  committed.
- **Authorization.** Every message/conversation endpoint checks membership;
  group add/remove checks the admin role. You cannot read or post to a
  conversation you're not in.
- **Encryption.** As the brief allows, end-to-end encryption is **simulated**
  (a UI label), not implemented.

---

## 10. Intentionally mocked or omitted, and how I'd extend it

- **Voice/video calls, Stories, Linked devices** — placeholders ("Coming soon"),
  as the brief permits.
- **Attachments, reactions, disappearing messages** — bonus items, not built.
  (Reply-to / quoted messages **is** built — see section 5.5 — via a nullable
  `reply_to_id` foreign key rather than the spoofable string-prefix hack.)
- **Real OTP** — replace `generate_mock_otp` with an SMS provider call; the
  surrounding flow already fits.

---

## 11. Scaling: what breaks first

The one piece of state that isn't in the database is the socket registry in
`manager.py`. It lives in a single process, so the app as written scales
**vertically** (one bigger server) but not **horizontally** (many servers)
— two users connected to two different instances wouldn't see each other's
messages, because each instance only knows its own sockets.

The standard fix, and what I'd reach for next: put a **Redis Pub/Sub** channel
between instances. When instance A needs to deliver to a user, it publishes the
event; every instance is subscribed and delivers to whichever of its *local*
sockets belong to that user. The `manager` interface (`send_to_user`,
`broadcast`) stays the same — only its internals change — which is exactly why
the broadcast logic was isolated behind that interface. Beyond that: move from
SQLite to PostgreSQL (one connection-string change), add message-history
pagination indexes (already present), and consider a read-through cache for
conversation lists.
