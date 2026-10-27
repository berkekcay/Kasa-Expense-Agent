// Chat with the coordinator agent (shared): plain and streamed turns, attached files, cards.
import { post, request, requestResponse, upload } from "./client";

export type ChartSpec = {
  type: "bar" | "line" | "pie" | "table";
  title: string;
  x: string;
  y: string;
  columns?: string[]; // table: the result columns in order
  data: Record<string, string | number | boolean | null>[];
};

export type ExpenseCard = {
  kind: "expense";
  data: { expense_id: number; merchant: string; total: string; currency: string; date?: string; house: boolean; split_type?: string };
};
export type PaymentCard = {
  kind: "payment";
  data: { payment_id: number; from: string; to: string; amount: string; currency: string };
};
export type ImportCard = {
  kind: "import";
  data: {
    draft_id: string;
    file: string;
    count: number;
    totals: { currency: string; total: string }[];
    first: string;
    last: string;
    sample: { date: string; description: string; amount: string; currency: string }[];
    skipped: number;
  };
};
export type ChatCard = ExpenseCard | PaymentCard | ImportCard;

export type ChatReply = {
  session_id: string;
  text: string;
  chart: ChartSpec | null;
  agent?: string | null;
  cards?: ChatCard[];
  conversation_id?: string | null;
  message_id?: number | null;
};

export type Conversation = { id: string; title: string; created_at: string; updated_at: string; message_count: number };
export type SavedMessage = {
  id: number;
  role: "user" | "assistant";
  text: string;
  created_at: string;
  chart: ChartSpec | null;
  agent: string | null;
  cards: ChatCard[];
  card_state: Record<string, Record<string, unknown>>;
  files: { name: string; kind: "sheet" | "image" }[];
};
export type ConversationDetail = Conversation & { messages: SavedMessage[] };

export type ChatFile = { file_id: string; filename: string; sheets: { name: string; rows: number; columns: string[] }[] };

export type ChatRequest = {
  message: string;
  session_id?: string | null;
  conversation_id?: string | null;
  file_ids?: string[];
  locale?: "tr" | "en";
};

/** What the streamed turn reports while it works. */
export type ChatEvent =
  | { type: "conversation"; conversation_id: string }
  | { type: "agent"; agent: string }
  | { type: "tool"; name: string }
  | { type: "tool_done"; name: string; status: string }
  | { type: "final"; reply: ChatReply }
  | { type: "error"; detail: string };

export const chatApi = {
  chat: (message: string, sessionId?: string | null, signal?: AbortSignal) =>
    request<ChatReply>("/chat", { ...post({ message, session_id: sessionId ?? null }), signal }),

  /** One turn as newline-delimited JSON events; resolves with the final reply. */
  chatStream: async (body: ChatRequest, onEvent: (e: ChatEvent) => void, signal?: AbortSignal): Promise<ChatReply> => {
    const res = await requestResponse("/chat/stream", { ...post(body), signal });
    const reader = res.body?.getReader();
    if (!reader) throw new Error("No response body");
    const decoder = new TextDecoder();
    let buffer = "";
    for (;;) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done });
      let newline = buffer.indexOf("\n");
      while (newline >= 0) {
        const line = buffer.slice(0, newline).trim();
        buffer = buffer.slice(newline + 1);
        newline = buffer.indexOf("\n");
        if (!line) continue;
        const event = JSON.parse(line) as ChatEvent;
        if (event.type === "final") return event.reply;
        if (event.type === "error") throw new Error(event.detail);
        onEvent(event);
      }
      if (done) break;
    }
    throw new Error("The answer stopped before it finished. Try again.");
  },

  uploadChatFile: (file: File) => request<ChatFile>("/chat/files", upload(file)),
  chatReceipt: (file: File, conversationId?: string | null) =>
    request<ChatReply>(`/chat/receipt${conversationId ? `?conversation_id=${encodeURIComponent(conversationId)}` : ""}`, upload(file)),
  listConversations: () => request<Conversation[]>("/chat/conversations"),
  getConversation: (id: string) => request<ConversationDetail>(`/chat/conversations/${encodeURIComponent(id)}`),
  renameConversation: (id: string, title: string) =>
    request<Conversation>(`/chat/conversations/${encodeURIComponent(id)}`, { method: "PATCH", body: JSON.stringify({ title }) }),
  deleteConversation: (id: string) => request<void>(`/chat/conversations/${encodeURIComponent(id)}`, { method: "DELETE" }),
  setCardState: (messageId: number, index: number, state: Record<string, unknown>) =>
    request<void>(`/chat/messages/${messageId}/cards/${index}`, { method: "PUT", body: JSON.stringify({ state }) }),
  confirmChatImport: (draftId: string) =>
    request<{ created: number; duplicates: number }>(`/chat/imports/${encodeURIComponent(draftId)}`, { method: "POST" }),
};
