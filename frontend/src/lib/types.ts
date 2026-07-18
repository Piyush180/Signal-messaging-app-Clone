// Shared types mirroring the backend Pydantic schemas. Keeping these in one
// place means a change to the API shape is a one-file update on the frontend.

export type MessageStatus = "sending" | "sent" | "delivered" | "read";

export interface User {
  id: number;
  phone_number: string;
  full_name: string | null;
  avatar_url: string | null;
  bio: string | null;
  is_online: boolean;
  last_seen: string | null;
  created_at: string;
}

export interface Member {
  user: User;
  role: "admin" | "member";
}

// Compact preview of a quoted message, rendered inside a reply bubble.
export interface QuotedMessage {
  id: number;
  sender_id: number;
  sender_name: string;
  content: string;
  message_type: string;
}

export interface Message {
  id: number;
  conversation_id: number;
  sender: User;
  content: string;
  message_type: "text" | "system";
  created_at: string;
  status: MessageStatus;
  client_id?: string | null;
  reply_to?: QuotedMessage | null;
  // Frontend-only: true while an optimistic message awaits server confirmation.
  pending?: boolean;
}

export interface GroupMetadata {
  id: number;
  conversation_id: number;
  name: string;
  description: string | null;
  avatar_url: string | null;
  created_by: number;
  created_at: string;
}

export interface Conversation {
  id: number;
  type: "direct" | "group";
  created_at: string;
  updated_at: string;
  members: Member[];
  group_metadata: GroupMetadata | null;
  last_message: Message | null;
  unread_count: number;
}

export interface Contact {
  id: number;
  user_id: number;
  contact_user: User;
  nickname: string | null;
  created_at: string;
}

export interface MessagePage {
  messages: Message[];
  has_more: boolean;
  next_cursor: number | null;
}

// Discriminated union of every event the server can push over the socket.
export type ServerEvent =
  | { type: "pong" }
  | { type: "new_message"; message: Message }
  | { type: "typing"; conversation_id: number; user_id: number; is_typing: boolean }
  | { type: "presence"; user_id: number; is_online: boolean; last_seen: string | null }
  | { type: "read_receipt"; conversation_id: number; reader_id: number; up_to_message_id: number }
  | { type: "delivered"; conversation_id: number; user_id: number; up_to_message_id: number };
