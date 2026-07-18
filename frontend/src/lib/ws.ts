// A small WebSocket wrapper that survives drops.
//
// Three things the raw browser WebSocket does NOT do for you — and without
// them, any network blip silently stops the app from receiving messages:
//   1) Reconnect automatically (with exponential backoff so we don't hammer a
//      server that is still down).
//   2) Send a periodic heartbeat ("ping") so a half-open connection is noticed.
//   3) Re-authenticate on every reconnect using the current token.
//
// It exposes a tiny interface: connect(), close(), send(), and an onEvent hook.

import { WS_BASE } from "./config";
import type { ServerEvent } from "./types";

type EventHandler = (event: ServerEvent) => void;
type StatusHandler = (connected: boolean) => void;

const HEARTBEAT_MS = 25000;
const MAX_BACKOFF_MS = 15000;

export class ReconnectingSocket {
  private ws: WebSocket | null = null;
  private token: string;
  private onEvent: EventHandler;
  private onStatus: StatusHandler;
  private heartbeat: ReturnType<typeof setInterval> | null = null;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private attempts = 0;
  private closedByUs = false;

  constructor(token: string, onEvent: EventHandler, onStatus: StatusHandler) {
    this.token = token;
    this.onEvent = onEvent;
    this.onStatus = onStatus;
  }

  connect() {
    this.closedByUs = false;
    const url = `${WS_BASE}/ws?token=${encodeURIComponent(this.token)}`;
    const ws = new WebSocket(url);
    this.ws = ws;

    ws.onopen = () => {
      this.attempts = 0;
      this.onStatus(true);
      this.startHeartbeat();
    };

    ws.onmessage = (evt) => {
      try {
        const data = JSON.parse(evt.data) as ServerEvent;
        if (data.type === "pong") return; // heartbeat ack, nothing to do
        this.onEvent(data);
      } catch {
        /* ignore malformed frames */
      }
    };

    ws.onclose = () => {
      this.onStatus(false);
      this.stopHeartbeat();
      if (!this.closedByUs) this.scheduleReconnect();
    };

    // onerror is followed by onclose; let onclose own the reconnect.
    ws.onerror = () => ws.close();
  }

  private scheduleReconnect() {
    // 0.5s, 1s, 2s, 4s ... capped. Keeps a downed server from being flooded.
    const delay = Math.min(500 * 2 ** this.attempts, MAX_BACKOFF_MS);
    this.attempts += 1;
    this.reconnectTimer = setTimeout(() => this.connect(), delay);
  }

  private startHeartbeat() {
    this.stopHeartbeat();
    this.heartbeat = setInterval(() => this.send({ type: "ping" }), HEARTBEAT_MS);
  }

  private stopHeartbeat() {
    if (this.heartbeat) clearInterval(this.heartbeat);
    this.heartbeat = null;
  }

  send(data: unknown) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
      return true;
    }
    return false;
  }

  close() {
    this.closedByUs = true;
    this.stopHeartbeat();
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.ws?.close();
    this.ws = null;
  }
}
