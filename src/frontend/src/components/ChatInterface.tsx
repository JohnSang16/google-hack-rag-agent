import { useEffect, useRef, useState } from 'react';
import type { HistoryItem, Message } from '../types';
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
  { label: 'RECALL', query: 'What were the key logistics challenges at Hacklanta?', color: '#93c5fd' },
  { label: 'ANALYZE', query: 'How has our event attendance grown over time?', color: '#c4b5fd' },
  { label: 'PLAN', query: 'Draft a planning brief for our next major hackathon.', color: '#86efac' },
];

export default function ChatInterface() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [inputValue, setInputValue] = useState('');
  const bottomRef = useRef<HTMLDivElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  function handleStop() {
    abortControllerRef.current?.abort();
    setLoading(false);
  }

  async function handleSendMessage(query: string, _model: string) { // eslint-disable-line @typescript-eslint/no-unused-vars
    if (!query.trim() || loading) return;

    const history: HistoryItem[] = messages
      .slice(-4)
      .filter((m) => m.role === 'user' || m.role === 'agent')
      .map((m) => ({
        role: m.role as 'user' | 'agent',
        content: m.role === 'agent'
          ? (m as { content: string }).content.slice(0, 400)
          : (m as { content: string }).content,
      }));

    setMessages((prev) => [
      ...prev,
      { role: 'user', content: query },
      { role: 'agent', content: '', mode: 'RECALL' as const, citations: [], created_doc_url: undefined, summary: undefined },
    ]);
    setLoading(true);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      const response = await fetch(`${API_BASE}/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, history }),
        signal: controller.signal,
      });

      if (!response.ok || !response.body) throw new Error(`HTTP ${response.status}`);

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buf = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const lines = buf.split('\n');
        buf = lines.pop() ?? '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          try {
            const ev = JSON.parse(line.slice(6));
            setMessages((prev) => {
              const msgs = [...prev];
              const last = msgs[msgs.length - 1];
              if (last?.role !== 'agent') return prev;
              if (ev.type === 'mode')  return [...msgs.slice(0, -1), { ...last, mode: ev.mode }];
              if (ev.type === 'token') return [...msgs.slice(0, -1), { ...last, content: last.content + ev.content }];
              if (ev.type === 'done')  return [...msgs.slice(0, -1), { ...last, mode: ev.mode, citations: ev.citations ?? [], created_doc_url: ev.created_doc_url, summary: ev.summary }];
              return prev;
            });
          } catch { /* ignore malformed SSE lines */ }
        }
      }
    } catch (err: unknown) {
      if (err instanceof Error && err.name === 'AbortError') {
        setMessages((prev) => {
          const last = prev[prev.length - 1];
          if (last?.role === 'agent' && last.content === '') return prev.slice(0, -1);
          return prev;
        });
        return;
      }
      setMessages((prev) => {
        const msgs = [...prev];
        if (msgs[msgs.length - 1]?.role === 'agent') msgs.pop();
        return [...msgs, { role: 'error' as const, content: 'Something went wrong. Is the backend running?' }];
      });
    } finally {
      setLoading(false);
    }
  }

  const isEmpty = messages.length === 0 && !loading;

  const inputArea = (
    <div className="w-full max-w-2xl mx-auto">
      <ClaudeChatInput
        onSendMessage={handleSendMessage}
        onStop={handleStop}
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
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium border transition-all hover:bg-white/5 disabled:opacity-40"
            style={{ color: s.color, background: 'transparent', borderColor: s.color + '55' }}
          >
            <span className="font-bold tracking-wide">{s.label}</span>
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
