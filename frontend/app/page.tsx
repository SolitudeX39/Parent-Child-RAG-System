"use client";

import { FormEvent, useCallback, useEffect, useRef, useState } from "react";

type Source = {
  page?: number | null;
  text: string;
  filename?: string | null;
  document_id?: string | null;
};

type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
};

type DocumentItem = {
  name: string;
  id: string;
  chunks?: number;
};

type DocumentPage = {
  page: number | null;
  text: string;
};

type DocumentDetail = {
  name: string;
  id: string;
  pages: DocumentPage[];
};

const API = "/rag";
const FALLBACK_PROMPTS = [
  "Diagnosis ต่างจาก Prognosis อย่างไร?",
  "Hyper- กับ Hypo- แปลว่าอะไร?",
  "Myocardial infarction คืออะไร?",
  "คำย่อ NPO และ PRN หมายถึงอะไร?",
];

async function readError(res: Response) {
  try {
    const data = await res.json();
    const detail = data.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail.map((item) => item.msg || JSON.stringify(item)).join(", ");
    }
    return data.message || res.statusText;
  } catch {
    return res.statusText;
  }
}

export default function Home() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [prompts, setPrompts] = useState<string[]>(FALLBACK_PROMPTS);
  const [error, setError] = useState("");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [viewer, setViewer] = useState<DocumentDetail | null>(null);
  const [viewerLoading, setViewerLoading] = useState(false);
  const [activePage, setActivePage] = useState<number | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const pageRefs = useRef<Record<number, HTMLElement | null>>({});

  const loadDocuments = useCallback(async () => {
    try {
      const res = await fetch(`${API}/documents`);
      if (!res.ok) return;
      const data = await res.json();
      setDocuments(data.documents || []);
    } catch {
      // backend may be offline during first paint
    }
  }, []);

  useEffect(() => {
    loadDocuments();
    fetch(`${API}/prompts`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data?.prompts?.length) setPrompts(data.prompts);
      })
      .catch(() => undefined);
  }, [loadDocuments]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy]);

  useEffect(() => {
    if (activePage == null) return;
    pageRefs.current[activePage]?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [viewer, activePage]);

  async function openDocument(documentId: string, page?: number | null) {
    setViewerLoading(true);
    setError("");
    try {
      const res = await fetch(`${API}/documents/${encodeURIComponent(documentId)}`);
      if (!res.ok) throw new Error(await readError(res));
      const data = (await res.json()) as DocumentDetail;
      setViewer(data);
      setActivePage(typeof page === "number" ? page : data.pages[0]?.page ?? null);
      setSidebarOpen(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "เปิดเอกสารไม่สำเร็จ");
    } finally {
      setViewerLoading(false);
    }
  }

  async function uploadPdf(file: File) {
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      setError("กรุณาเลือกไฟล์ PDF เท่านั้น");
      return;
    }

    setError("");
    setUploading(true);
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch(`${API}/upload`, { method: "POST", body: form });
      if (!res.ok) throw new Error(await readError(res));
      const data = await res.json();
      await loadDocuments();
      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          content: `อ่านเอกสาร ${data.filename} แล้วครับ มี ${data.parent_chunks} ช่วงเนื้อหาให้ถามได้ อยากให้สรุปภาพรวม หรือเจาะหัวข้อไหนก่อน?`,
        },
      ]);
      setSidebarOpen(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "อัปโหลดไม่สำเร็จ");
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  async function send(text: string, event?: FormEvent) {
    event?.preventDefault();
    const prompt = text.trim();
    if (!prompt || busy) return;

    const history = messages.map(({ role, content }) => ({ role, content }));
    const nextMessages: ChatMessage[] = [...messages, { role: "user", content: prompt }];
    setMessages(nextMessages);
    setInput("");
    setBusy(true);
    setError("");

    try {
      const res = await fetch(`${API}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: prompt, history }),
      });
      if (!res.ok) throw new Error(await readError(res));
      const data = await res.json();
      setMessages([
        ...nextMessages,
        {
          role: "assistant",
          content: data.answer || "ไม่พบคำตอบ",
          sources: data.sources || [],
        },
      ]);
    } catch (err) {
      const message = err instanceof Error ? err.message : "ส่งคำถามไม่สำเร็จ";
      setError(message);
      setMessages([
        ...nextMessages,
        {
          role: "assistant",
          content: `ส่งคำถามไม่สำเร็จ: ${message}`,
        },
      ]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex h-dvh overflow-hidden bg-[var(--paper)] text-[var(--ink)]">
      {sidebarOpen && (
        <button
          type="button"
          className="fixed inset-0 z-20 bg-black/40 md:hidden"
          aria-label="ปิดเมนู"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      <aside
        className={`fixed inset-y-0 left-0 z-30 flex w-[min(20rem,88vw)] flex-col bg-[var(--ink)] text-[#f4eadb] transition-transform md:static md:z-0 md:w-80 md:translate-x-0 ${
          sidebarOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="border-b border-white/10 px-5 py-5">
          <p className="text-xs tracking-[0.2em] text-[#e39a3a]">PARENT-CHILD RAG</p>
          <h1 className="mt-2 text-2xl font-semibold">ห้องถามเอกสาร</h1>
          <p className="mt-2 text-sm text-[#d8c7b2]">
            กดชื่อไฟล์เพื่ออ่านเนื้อหาที่ดึงมา แล้วคุยกับแชทเหมือนมีคนอ่านเอกสารให้
          </p>
        </div>

        <div className="px-5 py-4">
          <label
            onDragOver={(event) => {
              event.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(event) => {
              event.preventDefault();
              setDragOver(false);
              const file = event.dataTransfer.files?.[0];
              if (file) void uploadPdf(file);
            }}
            className={`flex cursor-pointer flex-col items-center rounded-2xl border border-dashed px-4 py-8 text-center transition ${
              dragOver
                ? "border-[#e39a3a] bg-white/10"
                : "border-white/20 bg-white/5 hover:bg-white/10"
            }`}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept="application/pdf,.pdf"
              className="hidden"
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (file) void uploadPdf(file);
              }}
            />
            <span className="text-sm font-medium">
              {uploading ? "กำลัง index เอกสาร..." : "วางไฟล์ PDF ที่นี่"}
            </span>
            <span className="mt-1 text-xs text-[#d8c7b2]">หรือคลิกเพื่อเลือกไฟล์</span>
          </label>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-5 pb-5">
          <p className="mb-2 text-xs tracking-wide text-[#d8c7b2]">เอกสารในระบบ</p>
          {documents.length === 0 ? (
            <p className="text-sm text-[#b9a48e]">ยังไม่มีไฟล์ที่ index</p>
          ) : (
            <ul className="space-y-2">
              {documents.map((doc) => (
                <li key={doc.id}>
                  <button
                    type="button"
                    onClick={() => void openDocument(doc.id)}
                    className={`w-full rounded-xl px-3 py-2 text-left text-sm leading-snug transition hover:bg-white/15 ${
                      viewer?.id === doc.id ? "bg-white/20" : "bg-white/10"
                    }`}
                  >
                    <span className="block font-medium">{doc.name}</span>
                    <span className="mt-1 block text-xs text-[#d8c7b2]">
                      กดเพื่อดูเนื้อหา
                      {typeof doc.chunks === "number" ? ` · ${doc.chunks} ช่วง` : ""}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </aside>

      <main className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-[var(--line)] px-4 py-3 md:px-6">
          <div className="flex items-center gap-3">
            <button
              type="button"
              className="rounded-lg border border-[var(--line)] px-3 py-1 text-sm md:hidden"
              onClick={() => setSidebarOpen(true)}
            >
              เอกสาร
            </button>
            <div>
              <p className="font-semibold">Chatbot</p>
              <p className="text-xs text-[var(--ink-soft)]">คุยจากเอกสารที่เปิดหรืออัปโหลดไว้</p>
            </div>
          </div>
          <button
            type="button"
            className="rounded-full border border-[var(--line)] px-3 py-1 text-sm hover:bg-black/5"
            onClick={() => {
              setMessages([]);
              setError("");
            }}
          >
            ล้างแชท
          </button>
        </header>

        <div className="flex-1 overflow-y-auto px-4 py-6 md:px-10">
          {messages.length === 0 && (
            <div className="mx-auto mt-10 max-w-xl rounded-3xl border border-[var(--line)] bg-[var(--paper-2)] p-8">
              <p className="text-lg font-semibold">เริ่มคุยจากเอกสารได้เลย</p>
              <p className="mt-2 text-sm text-[var(--ink-soft)]">
                กดชื่อไฟล์ทางซ้ายเพื่ออ่านเนื้อหา หรือเลือกประโยคด้านล่างเพื่อเริ่มถาม
              </p>
              <div className="mt-5 flex flex-wrap gap-2">
                {prompts.map((prompt) => (
                  <button
                    key={prompt}
                    type="button"
                    disabled={busy}
                    onClick={() => void send(prompt)}
                    className="rounded-full border border-[var(--line)] bg-white px-3 py-2 text-left text-sm hover:border-[var(--accent)] hover:text-[var(--accent)] disabled:opacity-50"
                  >
                    {prompt}
                  </button>
                ))}
              </div>
            </div>
          )}

          <div className="mx-auto flex max-w-3xl flex-col gap-4">
            {messages.map((message, index) => (
              <article
                key={`${message.role}-${index}`}
                className={`max-w-[90%] rounded-3xl px-4 py-3 leading-relaxed ${
                  message.role === "user"
                    ? "ml-auto bg-[var(--ink)] text-[#f7f1e4]"
                    : "bg-[#fffdf8] shadow-[0_8px_24px_rgba(36,28,22,0.08)]"
                }`}
              >
                <p className="whitespace-pre-wrap">{message.content.replaceAll("**", "")}</p>
                {message.sources && message.sources.length > 0 && (
                  <div className="mt-3 space-y-2 border-t border-[var(--line)] pt-2">
                    {message.sources.map((source, sourceIndex) => (
                      <div key={sourceIndex} className="text-sm">
                        <button
                          type="button"
                          className="cursor-pointer text-left text-[var(--accent)] underline-offset-2 hover:underline"
                          onClick={() => {
                            if (source.document_id) {
                              void openDocument(source.document_id, source.page);
                            }
                          }}
                        >
                          ดูเอกสาร
                          {source.filename ? ` · ${source.filename}` : ""}
                          {typeof source.page === "number" ? ` · หน้า ${source.page + 1}` : ""}
                        </button>
                        <p className="mt-2 max-h-28 overflow-y-auto whitespace-pre-wrap text-[var(--ink-soft)]">
                          {source.text}
                        </p>
                      </div>
                    ))}
                  </div>
                )}
              </article>
            ))}
            {busy && (
              <p className="text-sm text-[var(--ink-soft)]">กำลังค้นเอกสารและร่างคำตอบ...</p>
            )}
            <div ref={bottomRef} />
          </div>
        </div>

        <div className="border-t border-[var(--line)] bg-[var(--paper-2)] px-4 py-4 md:px-10">
          {error && <p className="mx-auto mb-2 max-w-3xl text-sm text-[var(--accent)]">{error}</p>}
          <form onSubmit={(event) => void send(input, event)} className="mx-auto flex max-w-3xl gap-2">
            <input
              value={input}
              onChange={(event) => setInput(event.target.value)}
              placeholder="คุยต่อได้เลย เช่น สรุปหน้านี้ให้หน่อย..."
              className="flex-1 rounded-2xl border border-[var(--line)] bg-white px-4 py-3 outline-none focus:border-[var(--accent)]"
              disabled={busy}
            />
            <button
              type="submit"
              disabled={busy || !input.trim()}
              className="rounded-2xl bg-[var(--accent)] px-5 py-3 font-medium text-white disabled:opacity-50"
            >
              ส่ง
            </button>
          </form>
        </div>
      </main>

      {(viewer || viewerLoading) && (
        <section className="fixed inset-y-0 right-0 z-40 flex w-full max-w-xl flex-col border-l border-[var(--line)] bg-[#fffdf8] shadow-2xl md:static md:z-0 md:shadow-none">
          <header className="flex items-start justify-between gap-3 border-b border-[var(--line)] px-5 py-4">
            <div>
              <p className="text-xs tracking-wide text-[var(--ink-soft)]">กำลังอ่าน</p>
              <h2 className="mt-1 text-lg font-semibold leading-snug">
                {viewer?.name || "กำลังเปิดเอกสาร..."}
              </h2>
            </div>
            <button
              type="button"
              className="rounded-full border border-[var(--line)] px-3 py-1 text-sm"
              onClick={() => {
                setViewer(null);
                setActivePage(null);
              }}
            >
              ปิด
            </button>
          </header>
          <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
            {viewerLoading && <p className="text-sm text-[var(--ink-soft)]">กำลังโหลดเนื้อหา...</p>}
            {viewer?.pages.map((page, index) => (
              <article
                key={`${page.page}-${index}`}
                ref={(node) => {
                  if (typeof page.page === "number") pageRefs.current[page.page] = node;
                }}
                className={`mb-4 rounded-2xl border px-4 py-3 ${
                  activePage === page.page
                    ? "border-[var(--accent)] bg-[var(--paper-2)]"
                    : "border-[var(--line)]"
                }`}
              >
                <p className="text-xs font-medium text-[var(--accent)]">
                  หน้า {typeof page.page === "number" ? page.page + 1 : index + 1}
                </p>
                <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-[var(--ink-soft)]">
                  {page.text}
                </p>
              </article>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
