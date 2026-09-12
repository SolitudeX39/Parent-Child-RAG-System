export type StoredMessage = {
  role: "user" | "assistant";
  content: string;
  sources?: unknown[];
  graph?: unknown[];
};

export type ChatThread = {
  id: string;
  title: string;
  updatedAt: number;
  messages: StoredMessage[];
};

export type ChatAction = { type: "new" } | { type: "open"; id: string } | { type: "refresh" };

const THREADS_KEY = "rag-chat-threads";
const CURRENT_KEY = "rag-chat-current";
export const CHAT_EVENT = "rag-chat";

export function loadThreads(): ChatThread[] {
  try {
    const raw = localStorage.getItem(THREADS_KEY);
    const parsed = raw ? (JSON.parse(raw) as ChatThread[]) : [];
    return Array.isArray(parsed)
      ? parsed.sort((a, b) => b.updatedAt - a.updatedAt)
      : [];
  } catch {
    return [];
  }
}

export function saveThreads(threads: ChatThread[]) {
  localStorage.setItem(THREADS_KEY, JSON.stringify(threads.slice(0, 40)));
  window.dispatchEvent(new CustomEvent(CHAT_EVENT, { detail: { type: "refresh" } }));
}

export function getCurrentThreadId() {
  return localStorage.getItem(CURRENT_KEY) || "";
}

export function setCurrentThreadId(id: string) {
  if (id) localStorage.setItem(CURRENT_KEY, id);
  else localStorage.removeItem(CURRENT_KEY);
}

export function titleFromMessages(messages: StoredMessage[]) {
  const first = messages.find((item) => item.role === "user")?.content.trim() || "แชทใหม่";
  return first.length > 36 ? `${first.slice(0, 36)}…` : first;
}

export function upsertThread(id: string, messages: StoredMessage[]) {
  if (messages.length === 0) return;
  const threads = loadThreads().filter((item) => item.id !== id);
  threads.unshift({
    id,
    title: titleFromMessages(messages),
    updatedAt: Date.now(),
    messages,
  });
  setCurrentThreadId(id);
  saveThreads(threads);
}

export function deleteThread(id: string) {
  const threads = loadThreads().filter((item) => item.id !== id);
  saveThreads(threads);
  if (getCurrentThreadId() === id) setCurrentThreadId("");
}

export function emitChat(action: ChatAction) {
  window.dispatchEvent(new CustomEvent(CHAT_EVENT, { detail: action }));
}

export function newThreadId() {
  return `chat-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
}
