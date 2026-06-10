import { useEffect, useRef, useState } from 'react';
import axios from 'axios';
import type { ChatResponse, HistoryItem, Message } from '../types';
import MessageBubble from './MessageBubble';
import ClaudeChatInput from './ui/claude-style-chat-input';

const API_BASE = import.meta.env.VITE_API_URL ?? '';

const LOADING_MESSAGES = [
  'cooking…', 'locking in…', 'rizzing up the database…',
  'try-hard maxxing…', 'let him cook…', 'super saiyan mode activated…',
  'no cap searching the archives…', 'going feral on the docs…',
  'sigma retrieval arc…', 'glazing the vector index…',
  'ate and left no crumbs…', 'this is so real fr fr…',
  'we do a little institutional memory…', 'on my grind rn…',
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
    <div className="bubble bubble--typing">
      <span className="typing-text" style={{ opacity: visible ? 1 : 0, transition: 'opacity 0.3s ease' }}>
        {LOADING_MESSAGES[index]}
      </span>
      <div className="typing"><span /><span /><span /></div>
    </div>
  );
}

const SUGGESTIONS = [
  { label: 'RECALL', query: 'What were the key logistics challenges at Hacklanta?', color: '#60a5fa', bg: '#1e3a5f' },
  { label: 'ANALYZE', query: 'How has our event attendance grown over time?', color: '#a78bfa', bg: '#2e1f5e' },
  { label: 'PLAN', query: 'Draft a planning brief for our next major hackathon.', color: '#4ade80', bg: '#14391f' },
];

export default function ChatInterface() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [inputValue, setInputValue] = useState('');
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  async function handleSendMessage(query: string, _model: string) {
    if (!query.trim() || loading) return;

    setMessages((prev) => [...prev, { role: 'user', content: query }]);
    setLoading(true);

    try {
      const history: HistoryItem[] = messages
        .slice(-4)
        .filter((m) => m.role === 'user' || m.role === 'agent')
        .map((m) => ({
          role: m.role as 'user' | 'agent',
          content: m.role === 'agent'
            ? (m as { content: string }).content.slice(0, 400)
            : (m as { content: string }).content,
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
    }
  }

  const isEmpty = messages.length === 0 && !loading;

  const inputArea = (
    <div className="w-full max-w-2xl mx-auto">
      <ClaudeChatInput
        onSendMessage={handleSendMessage}
        loading={loading}
        inputValue={inputValue}
        onInputValueConsumed={() => setInputValue('')}
      />
      <div className="flex flex-wrap justify-center gap-2 mt-3">
        {SUGGESTIONS.map((s) => (
          <button
            key={s.label}
            onClick={() => setInputValue(s.query)}
            disabled={loading}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium border transition-all hover:opacity-80 disabled:opacity-40"
            style={{ color: s.color, background: s.bg + '22', borderColor: s.color + '44' }}
          >
            <span className="font-bold tracking-wide">{s.label}</span>
            <span className="hidden sm:inline font-normal opacity-60">{s.query}</span>
          </button>
        ))}
      </div>
    </div>
  );

  return (
    <div className="h-screen flex flex-col overflow-hidden" style={{ background: 'var(--bg-0)', fontFamily: 'var(--sans)' }}>

      {isEmpty ? (
        /* Empty state: everything centered together */
        <div className="flex-1 flex flex-col items-center justify-center px-4 pb-8">
          <div className="text-center mb-8">
            <span className="text-5xl mb-4 block" style={{ color: 'var(--accent)' }}>◆</span>
            <h1 className="text-3xl font-light mb-2" style={{ color: 'var(--text-200)' }}>
              progsu Intelligence Agent
            </h1>
            <p className="text-sm" style={{ color: 'var(--text-400)' }}>
              Your org's institutional memory. Ask anything.
            </p>
          </div>
          {inputArea}
        </div>
      ) : (
        /* Active state: messages + pinned input */
        <>
          <div className="flex-1 overflow-y-auto">
            <div className="max-w-2xl mx-auto px-4 py-8 flex flex-col gap-4">
              {messages.map((msg, i) => (
                <MessageBubble key={i} message={msg} />
              ))}
              {loading && <TypingIndicator />}
              <div ref={bottomRef} />
            </div>
          </div>
          <div className="flex-shrink-0 px-4 pb-6 pt-3" style={{ borderTop: '1px solid var(--bg-300)' }}>
            {inputArea}
          </div>
        </>
      )}

    </div>
  );
}
