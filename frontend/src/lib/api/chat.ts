// Chat with the coordinator agent (shared).
import { post, request } from "./client";

export type ChartSpec = {
  type: "bar" | "line" | "pie" | "table";
  title: string;
  x: string;
  y: string;
  data: Record<string, string | number | boolean | null>[];
};

export type ChatReply = { session_id: string; text: string; chart: ChartSpec | null; agent?: string | null };

export const chatApi = {
  chat: (message: string, sessionId?: string | null, signal?: AbortSignal) =>
    request<ChatReply>("/chat", { ...post({ message, session_id: sessionId ?? null }), signal }),
};
