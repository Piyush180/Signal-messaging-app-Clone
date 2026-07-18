"use client";

// Owns the single WebSocket for the logged-in user and exposes:
//   - `connected` status,
//   - typed send helpers,
//   - a `subscribe(handler)` so components/pages can react to server events.
//
// Components subscribe instead of reading a single "lastEvent" value, which
// avoids the race where a fast-arriving second event overwrites the first
// before a listener runs.

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import { TOKEN_KEY } from "@/lib/config";
import { ReconnectingSocket } from "@/lib/ws";
import type { ServerEvent } from "@/lib/types";
import { useAuth } from "./AuthContext";

type Handler = (e: ServerEvent) => void;

interface SocketContextValue {
  connected: boolean;
  subscribe: (h: Handler) => () => void;
  sendChat: (
    conversationId: number,
    content: string,
    clientId: string,
    replyToId?: number
  ) => boolean;
  sendTyping: (conversationId: number, isTyping: boolean) => void;
  sendRead: (conversationId: number) => void;
}

const SocketContext = createContext<SocketContextValue | null>(null);

export function SocketProvider({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  const socketRef = useRef<ReconnectingSocket | null>(null);
  const listeners = useRef<Set<Handler>>(new Set());
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    if (!user) return;
    const token = localStorage.getItem(TOKEN_KEY);
    if (!token) return;

    const socket = new ReconnectingSocket(
      token,
      (event) => listeners.current.forEach((h) => h(event)),
      setConnected
    );
    socket.connect();
    socketRef.current = socket;

    return () => {
      socket.close();
      socketRef.current = null;
      setConnected(false);
    };
  }, [user]);

  const subscribe = useCallback((h: Handler) => {
    listeners.current.add(h);
    return () => {
      listeners.current.delete(h);
    };
  }, []);

  const sendChat = useCallback(
    (conversationId: number, content: string, clientId: string, replyToId?: number) =>
      socketRef.current?.send({
        type: "chat_message",
        conversation_id: conversationId,
        content,
        client_id: clientId,
        reply_to_id: replyToId,
      }) ?? false,
    []
  );

  const sendTyping = useCallback((conversationId: number, isTyping: boolean) => {
    socketRef.current?.send({
      type: "typing",
      conversation_id: conversationId,
      is_typing: isTyping,
    });
  }, []);

  const sendRead = useCallback((conversationId: number) => {
    socketRef.current?.send({ type: "read_receipt", conversation_id: conversationId });
  }, []);

  return (
    <SocketContext.Provider
      value={{ connected, subscribe, sendChat, sendTyping, sendRead }}
    >
      {children}
    </SocketContext.Provider>
  );
}

export function useSocket() {
  const ctx = useContext(SocketContext);
  if (!ctx) throw new Error("useSocket must be used within SocketProvider");
  return ctx;
}
