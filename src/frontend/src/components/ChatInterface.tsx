import { useEffect, useRef, useState } from 'react';
import axios from 'axios';
import type { ChatResponse, Message } from '../types';

const API_BASE = import.meta.env.VITE_API_URL ?? '';
import MessageBubble from './MessageBubble';
import ModeSelector from './ModeSelector';

function TypingIndicator() {
  return (
    <div className="bubble bubble--agent bubble--typing">
      <div className="typing">
        <span /><span /><span />
      </div>
    </div>
  );
}

export default function ChatInterface() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const query = input.trim();
    if (!query || loading) return;

    setInput('');
    setMessages((prev) => [...prev, { role: 'user', content: query }]);
    setLoading(true);

    try {
      const { data } = await axios.post<ChatResponse>(`${API_BASE}/chat`, { query });
      setMessages((prev) => [
        ...prev,
        {
          role: 'agent',
          content: data.answer,
          mode: data.mode,
          citations: data.citations,
          created_doc_url: data.created_doc_url,
        },
      ]);
    } catch (err: unknown) {
      const msg =
        axios.isAxiosError(err) && err.response?.data?.detail
          ? err.response.data.detail
          : 'Something went wrong. Is the backend running?';
      setMessages((prev) => [...prev, { role: 'error', content: msg }]);
    } finally {
      setLoading(false);
      textareaRef.current?.focus();
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e as unknown as React.FormEvent);
    }
  }

  return (
    <div className="chat">
      <header className="chat__header">
        <div className="chat__title">
          <span className="chat__logo">◆</span>
          progsu Intelligence Agent
        </div>
        <p className="chat__subtitle">Ask anything about your org's history, trends, or plans.</p>
      </header>

      <div className="chat__messages">
        {messages.length === 0 && (
          <div className="chat__empty">
            <p>Start by asking a question. Try:</p>
            <ul>
              <li>"What were the key logistics challenges at Hacklanta?"</li>
              <li>"How has our event attendance grown over time?"</li>
              <li>"Draft a planning brief for our next major hackathon."</li>
            </ul>
          </div>
        )}
        {messages.map((msg, i) => (
          <MessageBubble key={i} message={msg} />
        ))}
        {loading && <TypingIndicator />}
        <div ref={bottomRef} />
      </div>

      <div className="chat__footer">
        <ModeSelector />
        <form className="chat__form" onSubmit={handleSubmit}>
          <textarea
            ref={textareaRef}
            className="chat__input"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about your org's history, trends, or plans…"
            rows={1}
            disabled={loading}
          />
          <button
            className="chat__send"
            type="submit"
            disabled={!input.trim() || loading}
          >
            Send
          </button>
        </form>
      </div>
    </div>
  );
}
