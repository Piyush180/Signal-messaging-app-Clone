"use client";

// The application shell. This is a Client Component because the whole app is
// interactive, authenticated, and real-time — there is no meaningful server-
// rendered content to show a logged-out visitor. (DESIGN.md explains why a chat
// app is one of the cases where a client-driven page is the right call in Next.)

import { useCallback, useEffect, useRef, useState } from "react";
import { useAuth } from "@/context/AuthContext";
import { useSocket } from "@/context/SocketContext";
import { api } from "@/lib/api";
import type { Conversation, Message, QuotedMessage, ServerEvent, User } from "@/lib/types";
import { AuthScreen } from "@/components/AuthScreen";
import { Sidebar } from "@/components/Sidebar";
import { ChatWindow } from "@/components/ChatWindow";
import { ContactsModal } from "@/components/ContactsModal";
import { NewGroupModal } from "@/components/NewGroupModal";
import { GroupInfoModal } from "@/components/GroupInfoModal";
import { SettingsModal } from "@/components/SettingsModal";

type Modal = "contacts" | "group" | "info" | "settings" | null;

export default function Page() {
  const { user, loading } = useAuth();
  const { connected, subscribe, sendChat, sendTyping, sendRead } = useSocket();

  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<number | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [hasMore, setHasMore] = useState(false);
  const [cursor, setCursor] = useState<number | null>(null);
  const [presence, setPresence] = useState<Record<number, boolean>>({});
  const [typing, setTyping] = useState<Record<number, number[]>>({});
  const [modal, setModal] = useState<Modal>(null);

  // Refs so the (once-registered) socket handler always sees the latest values
  // without needing to re-subscribe on every state change.
  const activeIdRef = useRef<number | null>(null);
  activeIdRef.current = activeId;
  const userRef = useRef<User | null>(null);
  userRef.current = user;

  const activeConv = conversations.find((c) => c.id === activeId) ?? null;

  const loadConversations = useCallback(async () => {
    try {
      setConversations(await api.getConversations());
    } catch {
      /* handled by 401 flow */
    }
  }, []);

  useEffect(() => {
    if (user) loadConversations();
  }, [user, loadConversations]);

  // Load history whenever the active conversation changes.
  useEffect(() => {
    if (!activeId) {
      setMessages([]);
      return;
    }
    let cancelled = false;
    api.getMessages(activeId, 30).then((page) => {
      if (cancelled) return;
      setMessages(page.messages);
      setHasMore(page.has_more);
      setCursor(page.next_cursor);
      // Opening a chat marks it read.
      sendRead(activeId);
      setConversations((prev) =>
        prev.map((c) => (c.id === activeId ? { ...c, unread_count: 0 } : c))
      );
    });
    return () => {
      cancelled = true;
    };
  }, [activeId, sendRead]);

  const loadOlder = useCallback(async () => {
    if (!activeId || !hasMore || cursor == null) return;
    const page = await api.getMessages(activeId, 30, cursor);
    setMessages((prev) => [...page.messages, ...prev]);
    setHasMore(page.has_more);
    setCursor(page.next_cursor);
  }, [activeId, hasMore, cursor]);

  // ---- single socket subscription for the whole app ----
  useEffect(() => {
    if (!user) return;
    const unsub = subscribe((evt: ServerEvent) => {
      const myId = userRef.current?.id;
      const currentActive = activeIdRef.current;

      if (evt.type === "presence") {
        setPresence((p) => ({ ...p, [evt.user_id]: evt.is_online }));
        return;
      }

      if (evt.type === "typing") {
        setTyping((t) => {
          const ids = new Set(t[evt.conversation_id] ?? []);
          if (evt.is_typing) ids.add(evt.user_id);
          else ids.delete(evt.user_id);
          return { ...t, [evt.conversation_id]: [...ids] };
        });
        // Safety: auto-clear a stuck "typing" if no follow-up arrives.
        if (evt.is_typing) {
          setTimeout(() => {
            setTyping((t) => {
              const ids = new Set(t[evt.conversation_id] ?? []);
              ids.delete(evt.user_id);
              return { ...t, [evt.conversation_id]: [...ids] };
            });
          }, 5000);
        }
        return;
      }

      if (evt.type === "new_message") {
        const msg = evt.message;
        if (msg.conversation_id === currentActive) {
          setMessages((prev) => {
            // Reconcile the optimistic bubble (matched by client_id).
            if (msg.client_id) {
              const idx = prev.findIndex((m) => m.client_id === msg.client_id);
              if (idx !== -1) {
                const copy = [...prev];
                copy[idx] = msg;
                return copy;
              }
            }
            if (prev.some((m) => m.id === msg.id)) return prev;
            return [...prev, msg];
          });
          // We're looking at it => mark read, and tell the server.
          if (msg.sender.id !== myId) sendRead(currentActive);
        }
        // Update the sidebar (last message, unread, ordering).
        setConversations((prev) => {
          const exists = prev.some((c) => c.id === msg.conversation_id);
          if (!exists) {
            loadConversations();
            return prev;
          }
          return prev
            .map((c) => {
              if (c.id !== msg.conversation_id) return c;
              const isActive = c.id === currentActive;
              const mine = msg.sender.id === myId;
              return {
                ...c,
                last_message: msg,
                updated_at: msg.created_at,
                unread_count:
                  isActive || mine ? 0 : (c.unread_count || 0) + 1,
              };
            })
            .sort(
              (a, b) =>
                new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
            );
        });
        return;
      }

      if (evt.type === "read_receipt") {
        if (evt.conversation_id === currentActive) {
          setMessages((prev) =>
            prev.map((m) =>
              m.sender.id === myId && m.id <= evt.up_to_message_id
                ? { ...m, status: "read" }
                : m
            )
          );
        }
        return;
      }

      if (evt.type === "delivered") {
        if (evt.conversation_id === currentActive) {
          setMessages((prev) =>
            prev.map((m) =>
              m.sender.id === myId &&
              m.id <= evt.up_to_message_id &&
              m.status === "sent"
                ? { ...m, status: "delivered" }
                : m
            )
          );
        }
        return;
      }
    });
    return unsub;
  }, [user, subscribe, sendRead, loadConversations]);

  // ---- actions ----
  const handleSend = useCallback(
    async (content: string, replyTo?: QuotedMessage | null) => {
      if (!activeId || !user) return;
      const clientId =
        typeof crypto !== "undefined" && "randomUUID" in crypto
          ? crypto.randomUUID()
          : `c${Date.now()}`;

      // Optimistic bubble shown immediately in "sending" state, quote included,
      // so a reply looks final the instant you hit send.
      const optimistic: Message = {
        id: -Date.now(),
        conversation_id: activeId,
        sender: user,
        content,
        message_type: "text",
        created_at: new Date().toISOString(),
        status: "sending",
        client_id: clientId,
        reply_to: replyTo ?? null,
        pending: true,
      };
      setMessages((prev) => [...prev, optimistic]);

      const sentOverSocket = sendChat(activeId, content, clientId, replyTo?.id);
      if (!sentOverSocket) {
        // Socket down => REST fallback. Same server logic runs either way.
        try {
          const saved = await api.sendMessage(activeId, content, clientId, replyTo?.id);
          setMessages((prev) =>
            prev.map((m) => (m.client_id === clientId ? saved : m))
          );
          loadConversations();
        } catch {
          setMessages((prev) =>
            prev.map((m) =>
              m.client_id === clientId ? { ...m, status: "sent", pending: false } : m
            )
          );
        }
      }
    },
    [activeId, user, sendChat, loadConversations]
  );

  const handleTyping = useCallback(
    (isTyping: boolean) => {
      if (activeId) sendTyping(activeId, isTyping);
    },
    [activeId, sendTyping]
  );

  const startDirect = useCallback(
    async (contactUserId: number) => {
      const conv = await api.createDirect(contactUserId);
      setModal(null);
      await loadConversations();
      setActiveId(conv.id);
    },
    [loadConversations]
  );

  const onGroupChanged = useCallback(
    (conv: Conversation) => {
      setConversations((prev) => {
        const rest = prev.filter((c) => c.id !== conv.id);
        return [conv, ...rest];
      });
      setActiveId(conv.id);
      setModal(null);
    },
    []
  );

  if (loading) return <div className="center-screen">Loading…</div>;
  if (!user) return <AuthScreen />;

  return (
    <div className={`app ${activeId ? "has-active" : ""}`}>
      <Sidebar
        me={user}
        conversations={conversations}
        activeId={activeId}
        presence={presence}
        typing={typing}
        connected={connected}
        onSelect={setActiveId}
        onOpenContacts={() => setModal("contacts")}
        onOpenNewGroup={() => setModal("group")}
        onOpenSettings={() => setModal("settings")}
      />

      <ChatWindow
        me={user}
        conversation={activeConv}
        messages={messages}
        presence={presence}
        typing={activeConv ? typing[activeConv.id] ?? [] : []}
        hasMore={hasMore}
        connected={connected}
        onSend={handleSend}
        onTyping={handleTyping}
        onLoadOlder={loadOlder}
        onBack={() => setActiveId(null)}
        onOpenInfo={() => setModal("info")}
      />

      {modal === "contacts" && (
        <ContactsModal onClose={() => setModal(null)} onMessage={startDirect} />
      )}
      {modal === "group" && (
        <NewGroupModal onClose={() => setModal(null)} onCreated={onGroupChanged} />
      )}
      {modal === "info" && activeConv && (
        <GroupInfoModal
          me={user}
          conversation={activeConv}
          presence={presence}
          onClose={() => setModal(null)}
          onChanged={onGroupChanged}
          onMessage={startDirect}
        />
      )}
      {modal === "settings" && <SettingsModal onClose={() => setModal(null)} />}
    </div>
  );
}
