import { useEffect, useRef, useState } from 'react';
import axios from 'axios';
import type { ChatResponse, HistoryItem, Message } from '../types';

const API_BASE = import.meta.env.VITE_API_URL ?? '';
import MessageBubble from './MessageBubble';
import ModeSelector from './ModeSelector';

const LOADING_MESSAGES = [
  'cooking…',
  'locking in…',
  'rizzing up the database…',
  'try-hard maxxing…',
  'let him cook…',
  'super saiyan mode activated…',
  'no cap searching the archives…',
  'going feral on the docs…',
  'sigma retrieval arc…',
  'glazing the vector index…',
  'ate and left no crumbs…',
  'this is so real fr fr…',
  'we do a little institutional memory…',
  'on my grind rn…',
  'NPC behavior detected, switching to main character mode…',
];

function TypingIndicator() {
  const [index, setIndex] = useState(0);
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    const fade = setInterval(() => {
      setVisible(false);
      setTimeout(() => {
        setIndex((prev) => {
          let next;
          do { next = Math.floor(Math.random() * LOADING_MESSAGES.length); } while (next === prev);
          return next;
        });
        setVisible(true);
      }, 300);
    }, 2000);
    return () => clearInterval(fade);
  }, []);

  return (
    <div className="bubble bubble--agent bubble--typing">
      <span
        className="typing-text"
        style={{ opacity: visible ? 1 : 0, transition: 'opacity 0.3s ease' }}
      >
        {LOADING_MESSAGES[index]}
      </span>
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
      // Build history from last 4 messages (2 back-and-forth turns) before this query
      const history: HistoryItem[] = messages
        .slice(-4)
        .filter((m) => m.role === 'user' || m.role === 'agent')
        .map((m) => ({
          role: m.role as 'user' | 'agent',
          content: m.role === 'agent' ? (m as { content: string }).content.slice(0, 400) : (m as { content: string }).content,
        }));

      const { data } = await axios.post<ChatResponse>(`${API_BASE}/chat`, { query, history });
      setMessages((prev) => [
        ...prev,
        {
          role: 'agent',
          content: data.answer,
          summary: data.summary,
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
            <div className="chat__suggestions">
              {[
                'What were the key logistics challenges at Hacklanta?',
                'How has our event attendance grown over time?',
                'Draft a planning brief for our next major hackathon.',
              ].map((prompt) => (
                <button
                  key={prompt}
                  className="chat__suggestion"
                  onClick={() => setInput(prompt)}
                  disabled={loading}
                >
                  {prompt}
                </button>
              ))}
            </div>
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
