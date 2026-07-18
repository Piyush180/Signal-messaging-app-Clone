// Helpers to derive display info from a conversation, so the Sidebar, chat
// header, and group modal all compute the title/avatar the same way.

import type { Conversation, User } from "./types";

export function otherMember(conv: Conversation, myId: number | undefined): User | null {
  const m = conv.members.find((x) => x.user.id !== myId);
  return m ? m.user : null;
}

export function convTitle(conv: Conversation, myId: number | undefined): string {
  if (conv.type === "group") return conv.group_metadata?.name ?? "Group";
  const other = otherMember(conv, myId);
  return other?.full_name || other?.phone_number || "Direct chat";
}

export function convAvatar(conv: Conversation, myId: number | undefined): string | null {
  if (conv.type === "group") return conv.group_metadata?.avatar_url ?? null;
  return otherMember(conv, myId)?.avatar_url ?? null;
}

export function isAdmin(conv: Conversation, userId: number | undefined): boolean {
  const m = conv.members.find((x) => x.user.id === userId);
  return m?.role === "admin";
}
