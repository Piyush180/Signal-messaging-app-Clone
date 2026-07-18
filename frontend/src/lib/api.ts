// Typed API client. Every network call goes through `request`, which attaches
// the auth token, sets a timeout, and turns non-2xx responses into thrown
// Errors carrying the server's `detail` message.

import { API_V1, TOKEN_KEY } from "./config";
import type { Contact, Conversation, Message, MessagePage, User } from "./types";

export interface AuthResult {
  access_token: string;
  token_type: string;
  user: User;
}

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string> | undefined),
  };
  if (token) headers.Authorization = `Bearer ${token}`;

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15000);

  try {
    const res = await fetch(`${API_V1}${path}`, {
      ...options,
      headers,
      signal: controller.signal,
    });

    if (res.status === 401 && typeof window !== "undefined") {
      // Token is bad/expired. Clear it and let the app fall back to the login
      // screen (AuthContext listens for this via a storage event).
      localStorage.removeItem(TOKEN_KEY);
      window.dispatchEvent(new Event("signal:unauthorized"));
    }

    if (!res.ok) {
      const body = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(body.detail || "Request failed");
    }

    // 204 No Content has an empty body.
    if (res.status === 204) return undefined as T;
    return (await res.json()) as T;
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new Error("The server took too long to respond.");
    }
    throw err;
  } finally {
    clearTimeout(timeout);
  }
}

export const api = {
  // --- auth ---
  requestOtp: (phone_number: string) =>
    request<{ message: string; phone_number: string; otp_demo: string }>(
      "/auth/request-otp",
      { method: "POST", body: JSON.stringify({ phone_number }) }
    ),
  verifyOtp: (phone_number: string, code: string, full_name?: string) =>
    request<AuthResult>("/auth/verify-otp", {
      method: "POST",
      body: JSON.stringify({ phone_number, code, full_name }),
    }),
  me: () => request<User>("/auth/me"),
  logout: () => request<{ message: string }>("/auth/logout", { method: "POST" }),

  // --- users ---
  updateProfile: (data: Partial<Pick<User, "full_name" | "avatar_url" | "bio">>) =>
    request<User>("/users/me", { method: "PUT", body: JSON.stringify(data) }),
  searchUsers: (q: string) =>
    request<User[]>(`/users/search?q=${encodeURIComponent(q)}`),

  // --- contacts ---
  getContacts: () => request<Contact[]>("/contacts"),
  addContact: (phone_number: string, nickname?: string) =>
    request<Contact>("/contacts", {
      method: "POST",
      body: JSON.stringify({ phone_number, nickname }),
    }),
  deleteContact: (id: number) =>
    request<void>(`/contacts/${id}`, { method: "DELETE" }),

  // --- conversations ---
  getConversations: () => request<Conversation[]>("/conversations"),
  getConversation: (id: number) => request<Conversation>(`/conversations/${id}`),
  createDirect: (contact_user_id: number) =>
    request<Conversation>("/conversations/direct", {
      method: "POST",
      body: JSON.stringify({ contact_user_id }),
    }),
  createGroup: (
    name: string,
    member_user_ids: number[],
    description?: string,
    avatar_url?: string
  ) =>
    request<Conversation>("/conversations/group", {
      method: "POST",
      body: JSON.stringify({ name, member_user_ids, description, avatar_url }),
    }),

  // --- group admin ---
  addGroupMembers: (conversationId: number, user_ids: number[]) =>
    request<Conversation>(`/groups/${conversationId}/members`, {
      method: "POST",
      body: JSON.stringify({ user_ids }),
    }),
  removeGroupMember: (conversationId: number, userId: number) =>
    request<Conversation>(`/groups/${conversationId}/members/${userId}`, {
      method: "DELETE",
    }),

  // --- messages ---
  getMessages: (conversationId: number, limit = 30, beforeId?: number) =>
    request<MessagePage>(
      `/conversations/${conversationId}/messages?limit=${limit}` +
        (beforeId ? `&before_id=${beforeId}` : "")
    ),
  sendMessage: (
    conversationId: number,
    content: string,
    client_id?: string,
    reply_to_id?: number
  ) =>
    request<Message>(`/conversations/${conversationId}/messages`, {
      method: "POST",
      body: JSON.stringify({ content, client_id, reply_to_id }),
    }),
};
