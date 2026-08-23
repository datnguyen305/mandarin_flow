"use client";

import { Bot, Loader2, MessageCircle, Send, X } from "lucide-react";
import { FormEvent, useState } from "react";
import { chatWithAssistant, type AssistantChatMessage } from "@/lib/api";

type ChatMessage = {
  id: number;
  role: "bot" | "user";
  text: string;
};

type ImportChatbotProps = {
  devToken?: string | null;
};

export function ImportChatbot({ devToken }: ImportChatbotProps) {
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([
    { id: 1, role: "bot", text: "Bạn có thể bảo tôi import một video bằng cách gửi link YouTube." },
  ]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = input.trim();
    if (!text || sending) return;

    setMessages((current) => [...current, { id: Date.now(), role: "user", text }]);
    setInput("");
    setSending(true);
    try {
      const history: AssistantChatMessage[] = messages.map((message) => ({
        role: message.role === "user" ? "user" : "assistant",
        content: message.text,
      }));
      const response = await chatWithAssistant(text, history, devToken);
      setMessages((current) => [
        ...current,
        { id: Date.now() + 1, role: "bot", text: response.reply },
      ]);
    } catch (error) {
      setMessages((current) => [
        ...current,
        { id: Date.now() + 1, role: "bot", text: error instanceof Error ? error.message : "Không thể import video." },
      ]);
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="fixed bottom-5 right-4 z-40 sm:right-6">
      {open ? (
        <section className="mb-3 flex h-[min(30rem,calc(100vh-7rem))] w-[min(22rem,calc(100vw-2rem))] flex-col overflow-hidden rounded-2xl border border-cream-200 bg-cream-50 shadow-xl">
          <header className="flex items-center justify-between border-b border-cream-200 bg-brand-700 px-4 py-3 text-cream-50">
            <div className="flex items-center gap-2">
              <Bot size={18} />
              <div>
                <h2 className="text-sm font-semibold">MandarinFlow Bot</h2>
                <p className="text-[11px] text-brand-100">Import video bằng hội thoại</p>
              </div>
            </div>
            <button aria-label="Đóng chatbot" className="rounded-lg p-1.5 transition hover:bg-brand-800" onClick={() => setOpen(false)} title="Đóng chatbot" type="button">
              <X size={17} />
            </button>
          </header>

          <div className="min-h-0 flex-1 space-y-3 overflow-y-auto p-3">
            {messages.map((message) => (
              <div className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`} key={message.id}>
                <p className={`max-w-[85%] rounded-2xl px-3 py-2 text-sm leading-5 ${message.role === "user" ? "rounded-br-md bg-brand-700 text-cream-50" : "rounded-bl-md bg-cream-100 text-slate-700"}`}>
                  {message.text}
                </p>
              </div>
            ))}
            {sending ? (
              <div className="flex items-center gap-2 text-xs text-slate-500">
                <Loader2 className="animate-spin" size={14} />
                Đang gửi yêu cầu...
              </div>
            ) : null}
          </div>

          <form className="flex gap-2 border-t border-cream-200 p-3" onSubmit={handleSubmit}>
            <input
              aria-label="Tin nhắn chatbot"
              className="min-w-0 flex-1 rounded-xl border border-cream-300 bg-cream-100/60 px-3 py-2 text-sm outline-none transition focus:border-brand-500 focus:ring-2 focus:ring-brand-100"
              disabled={sending}
              onChange={(event) => setInput(event.target.value)}
              placeholder="Import https://youtu.be/..."
              value={input}
            />
            <button aria-label="Gửi tin nhắn" className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-brand-700 text-cream-50 transition hover:bg-brand-800 disabled:cursor-not-allowed disabled:opacity-50" disabled={sending || !input.trim()} title="Gửi tin nhắn" type="submit">
              <Send size={16} />
            </button>
          </form>
        </section>
      ) : null}

      <button aria-expanded={open} aria-label={open ? "Đóng chatbot import video" : "Mở chatbot import video"} className="ml-auto inline-flex h-12 w-12 items-center justify-center rounded-full bg-brand-700 text-cream-50 shadow-lg transition hover:scale-105 hover:bg-brand-800" onClick={() => setOpen((current) => !current)} title={open ? "Đóng chatbot" : "Mở chatbot import video"} type="button">
        {open ? <X size={20} /> : <MessageCircle size={20} />}
      </button>
    </div>
  );
}
