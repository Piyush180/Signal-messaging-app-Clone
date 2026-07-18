"use client";

import { useState } from "react";
import { Search, UserPlus, Users, Settings, LogOut } from "lucide-react";
import type { Conversation, User } from "@/lib/types";
import { convAvatar, convTitle, otherMember } from "@/lib/conversation";
import { formatTime } from "@/lib/time";
import { useAuth } from "@/context/AuthContext";
import { Avatar } from "./Avatar";

interface Props {
  me: User;
  conversations: Conversation[];
  activeId: number | null;
  presence: Record<number, boolean>;
  typing: Record<number, number[]>;
  connected: boolean;
  onSelect: (id: number) => void;
  onOpenContacts: () => void;
  onOpenNewGroup: () => void;
  onOpenSettings: () => void;
}

export function Sidebar({
  me,
  conversations,
  activeId,
  presence,
  typing,
  connected,
  onSelect,
  onOpenContacts,
  onOpenNewGroup,
  onOpenSettings,
}: Props) {
  const { logout } = useAuth();
  const [q, setQ] = useState("");

  const filtered = conversations.filter((c) => {
    if (!q.trim()) return true;
    return convTitle(c, me.id).toLowerCase().includes(q.trim().toLowerCase());
  });

  const isOnline = (c: Conversation) => {
    if (c.type === "group") return false;
    const other = otherMember(c, me.id);
    if (!other) return false;
    return presence[other.id] ?? other.is_online;
  };

  return (
    <aside className="sidebar">
      <div className="sidebar-top">
        <div className="me" onClick={onOpenSettings}>
          <Avatar name={me.full_name} id={me.id} url={me.avatar_url} size={40} />
          <div>
            <div className="name">{me.full_name || "My profile"}</div>
            <div className="sub">{me.phone_number}</div>
          </div>
        </div>
        <div className="icon-row">
          <button className="icon-btn" title="New contact" onClick={onOpenContacts}>
            <UserPlus size={19} />
          </button>
          <button className="icon-btn" title="New group" onClick={onOpenNewGroup}>
            <Users size={19} />
          </button>
          <button className="icon-btn" title="Settings" onClick={onOpenSettings}>
            <Settings size={19} />
          </button>
          <button className="icon-btn" title="Log out" onClick={logout}>
            <LogOut size={19} />
          </button>
        </div>
      </div>

      <div className="search">
        <div className="search-box">
          <Search size={18} color="var(--text-muted)" />
          <input
            placeholder="Search"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
        </div>
      </div>

      {!connected && <div className="conn-banner">Reconnecting…</div>}

      <div className="conv-list">
        {filtered.length === 0 ? (
          <div style={{ padding: 24, textAlign: "center", color: "var(--text-muted)", fontSize: 13 }}>
            No conversations yet. Add a contact to start chatting.
          </div>
        ) : (
          filtered.map((c) => {
            const title = convTitle(c, me.id);
            const isTyping = (typing[c.id] ?? []).length > 0;
            const preview = isTyping
              ? "typing…"
              : c.last_message
              ? (c.last_message.message_type === "system"
                  ? c.last_message.content
                  : c.last_message.content)
              : "No messages yet";
            return (
              <div
                key={c.id}
                className={`conv ${c.id === activeId ? "active" : ""}`}
                onClick={() => onSelect(c.id)}
              >
                <Avatar
                  name={title}
                  id={c.id}
                  url={convAvatar(c, me.id)}
                  size={46}
                  showPresence={c.type === "direct"}
                  online={isOnline(c)}
                />
                <div className="body">
                  <div className="row">
                    <span className="title">{title}</span>
                    <span className="time">
                      {c.last_message ? formatTime(c.last_message.created_at) : ""}
                    </span>
                  </div>
                  <div className="row">
                    <span
                      className="preview"
                      style={isTyping ? { color: "var(--signal-blue)", fontWeight: 600 } : undefined}
                    >
                      {preview}
                    </span>
                    {c.unread_count > 0 && <span className="badge">{c.unread_count}</span>}
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>
    </aside>
  );
}
