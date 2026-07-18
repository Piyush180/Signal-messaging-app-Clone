"use client";

import { useEffect, useState } from "react";
import { MessageSquare, UserMinus, UserPlus, X } from "lucide-react";
import { api } from "@/lib/api";
import type { Contact, Conversation, User } from "@/lib/types";
import { convAvatar, convTitle, isAdmin } from "@/lib/conversation";
import { Avatar } from "./Avatar";

interface Props {
  me: User;
  conversation: Conversation;
  presence: Record<number, boolean>;
  onClose: () => void;
  onChanged: (conv: Conversation) => void;
  onMessage: (userId: number) => void;
}

export function GroupInfoModal({
  me, conversation, presence, onClose, onChanged, onMessage,
}: Props) {
  const isGroup = conversation.type === "group";
  const amAdmin = isAdmin(conversation, me.id);
  const creatorId = conversation.group_metadata?.created_by;

  const [contacts, setContacts] = useState<Contact[]>([]);
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (isGroup && amAdmin) api.getContacts().then(setContacts).catch(() => {});
  }, [isGroup, amAdmin]);

  const memberIds = new Set(conversation.members.map((m) => m.user.id));
  const addable = contacts.filter((c) => !memberIds.has(c.contact_user.id));

  const addMember = async (userId: number) => {
    setError("");
    try {
      const conv = await api.addGroupMembers(conversation.id, [userId]);
      onChanged(conv);
    } catch (err) {
      setError((err as Error).message);
    }
  };

  const removeMember = async (userId: number) => {
    setError("");
    try {
      const conv = await api.removeGroupMember(conversation.id, userId);
      onChanged(conv);
    } catch (err) {
      setError((err as Error).message);
    }
  };

  return (
    <div className="overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <h2>{isGroup ? "Group info" : "Contact info"}</h2>
          <button className="icon-btn" onClick={onClose}><X size={20} /></button>
        </div>

        <div style={{ textAlign: "center", marginBottom: 18 }}>
          <Avatar name={convTitle(conversation, me.id)} id={conversation.id}
            url={convAvatar(conversation, me.id)} size={72} />
          <h3 style={{ marginTop: 10 }}>{convTitle(conversation, me.id)}</h3>
          {conversation.group_metadata?.description && (
            <p style={{ color: "var(--text-muted)", fontSize: 13 }}>
              {conversation.group_metadata.description}
            </p>
          )}
          {isGroup && (
            <div style={{ color: "var(--signal-blue)", fontSize: 12, fontWeight: 600, marginTop: 4 }}>
              {conversation.members.length} members
            </div>
          )}
        </div>

        {error && <div className="alert-error">{error}</div>}

        <div className="field">
          <label>Members</label>
          {conversation.members.map((m) => {
            const online = presence[m.user.id] ?? m.user.is_online;
            const admin = m.role === "admin" || m.user.id === creatorId;
            const isMe = m.user.id === me.id;
            return (
              <div className="list-row" key={m.user.id}>
                <div className="who">
                  <Avatar name={m.user.full_name || m.user.phone_number} id={m.user.id}
                    url={m.user.avatar_url} size={38} showPresence online={online} />
                  <div>
                    <div style={{ fontWeight: 600, fontSize: 14, display: "flex", gap: 6, alignItems: "center" }}>
                      {m.user.full_name || m.user.phone_number}
                      {isMe && <span style={{ fontSize: 11, color: "var(--text-muted)" }}>(You)</span>}
                      {admin && <span className="pill-admin">Admin</span>}
                    </div>
                    <div style={{ fontSize: 12, color: "var(--text-muted)" }}>
                      {online ? "Online" : "Offline"}
                    </div>
                  </div>
                </div>
                <div className="icon-row">
                  {!isMe && (
                    <button className="icon-btn" title="Message" onClick={() => { onClose(); onMessage(m.user.id); }}>
                      <MessageSquare size={16} color="var(--signal-blue)" />
                    </button>
                  )}
                  {isGroup && amAdmin && !isMe && m.user.id !== creatorId && (
                    <button className="icon-btn" title="Remove from group" onClick={() => removeMember(m.user.id)}>
                      <UserMinus size={16} color="var(--danger)" />
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {isGroup && amAdmin && (
          <div className="field">
            <button className="btn btn-ghost" onClick={() => setAdding((a) => !a)}>
              <UserPlus size={16} style={{ verticalAlign: "middle", marginRight: 6 }} />
              {adding ? "Done" : "Add members"}
            </button>
            {adding && (
              <div style={{ marginTop: 10, maxHeight: 180, overflowY: "auto" }}>
                {addable.length === 0 ? (
                  <div style={{ fontSize: 13, color: "var(--text-muted)", padding: 8 }}>
                    All your contacts are already in this group.
                  </div>
                ) : (
                  addable.map((c) => (
                    <div className="list-row" key={c.id}>
                      <div className="who">
                        <Avatar name={c.contact_user.full_name} id={c.contact_user.id}
                          url={c.contact_user.avatar_url} size={34} />
                        <span style={{ fontSize: 14 }}>{c.nickname || c.contact_user.full_name}</span>
                      </div>
                      <button className="icon-btn" title="Add" onClick={() => addMember(c.contact_user.id)}>
                        <UserPlus size={16} color="var(--signal-blue)" />
                      </button>
                    </div>
                  ))
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
