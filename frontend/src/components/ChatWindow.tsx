"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowLeft, Check, CheckCheck, Clock, Info, Phone, Reply, Smile, Video, Send, Lock, X,
} from "lucide-react";
import type { Conversation, Message, QuotedMessage, User } from "@/lib/types";
import { convAvatar, convTitle, otherMember } from "@/lib/conversation";
import { dayKey, formatDayLabel, formatTime, lastSeenText } from "@/lib/time";
import { Avatar } from "./Avatar";

const EMOJIS = ["😊","😂","😍","👍","🙏","🎉","🔥","❤️","😎","🥳","🤔","😭","💯","👀","🚀","✨"];

interface Props {
  me: User;
  conversation: Conversation | null;
  messages: Message[];
  presence: Record<number, boolean>;
  typing: number[];
  hasMore: boolean;
  connected: boolean;
  onSend: (content: string, replyTo?: QuotedMessage | null) => void;
  onTyping: (isTyping: boolean) => void;
  onLoadOlder: () => void;
  onBack: () => void;
  onOpenInfo: () => void;
}

function Ticks({ status }: { status: Message["status"] }) {
  if (status === "sending") return <Clock size={13} className="ticks" />;
  if (status === "sent") return <Check size={14} className="ticks" />;
  if (status === "delivered") return <CheckCheck size={14} className="ticks" />;
  return <CheckCheck size={14} className="ticks read" />; // read
}

export function ChatWindow({
  me, conversation, messages, presence, typing, hasMore,
  connected, onSend, onTyping, onLoadOlder, onBack, onOpenInfo,
}: Props) {
  const [text, setText] = useState("");
  const [showEmoji, setShowEmoji] = useState(false);
  // The message being replied to; shown as a bar above the composer until
  // the reply is sent or cancelled (Esc / X), exactly like WhatsApp.
  const [replyTo, setReplyTo] = useState<QuotedMessage | null>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const typingTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const isGroup = conversation?.type === "group";

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length, typing.length]);

  // Switching chats discards a half-composed reply — it belongs to the old chat.
  useEffect(() => {
    setReplyTo(null);
  }, [conversation?.id]);

  const startReply = (m: Message) => {
    setReplyTo({
      id: m.id,
      sender_id: m.sender.id,
      sender_name: m.sender.full_name || m.sender.phone_number,
      content: m.content,
      message_type: m.message_type,
    });
    inputRef.current?.focus();
  };

  // Clicking a quote scrolls to (and briefly highlights) the original message,
  // if it is currently loaded.
  const jumpToMessage = (id: number) => {
    const el = document.getElementById(`msg-${id}`);
    if (!el) return;
    el.scrollIntoView({ behavior: "smooth", block: "center" });
    el.classList.add("flash");
    setTimeout(() => el.classList.remove("flash"), 1200);
  };

  const header = useMemo(() => {
    if (!conversation) return { title: "", sub: "", online: false, typing: false };
    const title = convTitle(conversation, me.id);
    if (typing.length > 0) {
      if (isGroup) {
        const name =
          conversation.members.find((m) => m.user.id === typing[0])?.user.full_name;
        return { title, sub: `${name || "Someone"} is typing…`, online: false, typing: true };
      }
      return { title, sub: "typing…", online: false, typing: true };
    }
    if (isGroup) {
      return { title, sub: `${conversation.members.length} members`, online: false, typing: false };
    }
    const other = otherMember(conversation, me.id);
    const online = other ? (presence[other.id] ?? other.is_online) : false;
    return {
      title,
      sub: online ? "Online" : lastSeenText(other?.last_seen ?? null),
      online,
      typing: false,
    };
  }, [conversation, me.id, typing, presence, isGroup]);

  if (!conversation) {
    return (
      <section className="chat">
        <div className="empty">
          <Lock size={44} color="var(--signal-blue)" />
          <h2>Signal Clone</h2>
          <p>Select a conversation to start messaging.<br />Messages are end-to-end encrypted (simulated).</p>
        </div>
      </section>
    );
  }

  const onInputChange = (v: string) => {
    setText(v);
    onTyping(true);
    if (typingTimer.current) clearTimeout(typingTimer.current);
    typingTimer.current = setTimeout(() => onTyping(false), 1800);
  };

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const value = text.trim();
    if (!value) return;
    onSend(value, replyTo);
    setText("");
    setReplyTo(null);
    onTyping(false);
    setShowEmoji(false);
  };

  let lastDay = "";

  return (
    <section className="chat">
      <div className="chat-header">
        <div className="who">
          <button className="icon-btn back-btn" onClick={onBack}>
            <ArrowLeft size={20} />
          </button>
          <Avatar
            name={header.title}
            id={conversation.id}
            url={convAvatar(conversation, me.id)}
            size={42}
          />
          <div>
            <div className="name">{header.title}</div>
            <div className={`status ${header.typing ? "typing" : header.online ? "online" : ""}`}>
              {header.sub}
            </div>
          </div>
        </div>
        <div className="icon-row">
          <button className="icon-btn" title="Voice call (coming soon)"><Phone size={18} /></button>
          <button className="icon-btn" title="Video call (coming soon)"><Video size={18} /></button>
          <button className="icon-btn" title="Details" onClick={onOpenInfo}><Info size={19} /></button>
        </div>
      </div>

      {!connected && <div className="conn-banner">Reconnecting…</div>}

      <div className="stream">
        {hasMore && (
          <button className="day-sep" style={{ cursor: "pointer" }} onClick={onLoadOlder}>
            Load earlier messages
          </button>
        )}
        <div className="system-pill">
          <Lock size={11} /> Messages are end-to-end encrypted (simulated)
        </div>

        {messages.map((m) => {
          const showDay = dayKey(m.created_at) !== lastDay;
          lastDay = dayKey(m.created_at);
          const dayEl = showDay ? (
            <div className="day-sep" key={`d-${m.id}`}>{formatDayLabel(m.created_at)}</div>
          ) : null;

          if (m.message_type === "system") {
            return (
              <div key={`w-${m.id}`}>
                {dayEl}
                <div className="system-pill">{m.content}</div>
              </div>
            );
          }

          const out = m.sender.id === me.id;
          return (
            <div key={`w-${m.id}`}>
              {dayEl}
              <div className={`bubble-row ${out ? "out" : "in"}`}>
                {!out && isGroup && (
                  <span className="sender-name">
                    {m.sender.full_name || m.sender.phone_number}
                  </span>
                )}
                <div className="bubble-wrap">
                  <div id={`msg-${m.id}`} className={`bubble ${out ? "out" : "in"}`}>
                    {m.reply_to && (
                      <button
                        type="button"
                        className="quote"
                        onClick={() => jumpToMessage(m.reply_to!.id)}
                        title="Go to original message"
                      >
                        <span className="quote-sender">
                          {m.reply_to.sender_id === me.id ? "You" : m.reply_to.sender_name}
                        </span>
                        <span className="quote-text">{m.reply_to.content}</span>
                      </button>
                    )}
                    {m.content}
                    <div className="meta">
                      <span>{formatTime(m.created_at)}</span>
                      {out && <Ticks status={m.status} />}
                    </div>
                  </div>
                  {!m.pending && (
                    <button
                      type="button"
                      className="reply-btn"
                      title="Reply"
                      onClick={() => startReply(m)}
                    >
                      <Reply size={15} />
                    </button>
                  )}
                </div>
              </div>
            </div>
          );
        })}

        {typing.length > 0 && (
          <div className="bubble-row in">
            <div className="bubble in typing-bubble">
              <span className="dot" /><span className="dot" /><span className="dot" />
            </div>
          </div>
        )}
        <div ref={endRef} />
      </div>

      <div className="composer">
        {replyTo && (
          <div className="reply-bar">
            <div className="reply-bar-body">
              <span className="quote-sender">
                Replying to {replyTo.sender_id === me.id ? "yourself" : replyTo.sender_name}
              </span>
              <span className="quote-text">{replyTo.content}</span>
            </div>
            <button
              type="button"
              className="icon-btn"
              title="Cancel reply"
              onClick={() => setReplyTo(null)}
            >
              <X size={16} />
            </button>
          </div>
        )}
        <form className="composer-row" onSubmit={submit} style={{ position: "relative" }}>
          {showEmoji && (
            <div className="emoji-pop">
              {EMOJIS.map((e) => (
                <button type="button" key={e} onClick={() => setText((t) => t + e)}>{e}</button>
              ))}
            </div>
          )}
          <button
            type="button"
            className="icon-btn"
            onClick={() => setShowEmoji((s) => !s)}
            title="Emoji"
          >
            <Smile size={22} color={showEmoji ? "var(--signal-blue)" : "var(--text-muted)"} />
          </button>
          <input
            ref={inputRef}
            placeholder="Message"
            value={text}
            onChange={(e) => onInputChange(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Escape") setReplyTo(null);
            }}
          />
          <button type="submit" className="send-btn" disabled={!text.trim()}>
            <Send size={18} />
          </button>
        </form>
      </div>
    </section>
  );
}
