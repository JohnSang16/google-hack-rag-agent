import { useEffect, useRef, useState } from 'react';
import type { AgentMessage, HistoryItem, Message } from '../types';
import type { Me } from '../auth';
import { authHeaders, captureTokenFromHash, clearToken, getToken } from '../auth';
import MessageBubble from './MessageBubble';
import DocPanel from './DocPanel';
import ClaudeChatInput from './ui/claude-style-chat-input';

const API_BASE = import.meta.env.VITE_API_URL ?? '';

const LOADING_MESSAGES = [
  'cooking…', 'locking in…', 'rizzing…', 'try-harding…', 'let him cook…',
  'i like ya cut g…', 'ouu shii…', 'we do a lil trollin…', 'chud maxxing…',
  'working hard or hardly working?…', 'big spoon or little spoon?…', 'js…', 'js + js…',
];

const FYM_MESSAGE = 'fym ouu shii?…';

function TypingIndicator() {
  const [text, setText] = useState(LOADING_MESSAGES[0]);
  const [visible, setVisible] = useState(true);
  const lastTextRef = useRef(LOADING_MESSAGES[0]);
  const nextForcedRef = useRef<string | null>(null);

  useEffect(() => {
    const fade = setInterval(() => {
      setVisible(false);
      setTimeout(() => {
        let next: string;
        if (nextForcedRef.current !== null) {
          next = nextForcedRef.current;
          nextForcedRef.current = null;
        } else {
          let pick: string;
          do {
            pick = LOADING_MESSAGES[Math.floor(Math.random() * LOADING_MESSAGES.length)];
          } while (pick === lastTextRef.current);
          next = pick;
          if (next === 'ouu shii…') nextForcedRef.current = FYM_MESSAGE;
        }
        lastTextRef.current = next;
        setText(next);
        setVisible(true);
      }, 300);
    }, 2000);
    return () => clearInterval(fade);
  }, []);

  return (
    <div className="bubble bubble--typing">
      <span className="typing-text" style={{ opacity: visible ? 1 : 0, transition: 'opacity 0.3s ease' }}>
        {text}
      </span>
      <div className="typing"><span /><span /><span /></div>
    </div>
  );
}

const SUGGESTIONS = [
  { label: 'RECALL', query: 'What were the key logistics challenges at Hacklanta and how did we solve them?', color: '#93c5fd', tip: 'Look up events, decisions, and outcomes' },
  { label: 'ANALYZE', query: 'How has our event attendance grown from Fall 2025 to Spring 2026, and which events drove the most engagement?', color: '#c4b5fd', tip: 'Spot trends and patterns across the org\'s history' },
  { label: 'PLAN', query: 'Create a sponsor packet for Hacklanta II with key metrics from Hacklanta 1, what we\'re improving, and how sponsors can get involved. Add it to our calendar and email our sponsors.', color: '#86efac', tip: 'Generate a doc, calendar event, and email draft' },
];

export default function ChatInterface() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [inputValue, setInputValue] = useState('');
  const [panelMsg, setPanelMsg] = useState<AgentMessage | null>(null);
  const [latestPlanDocUrl, setLatestPlanDocUrl] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const [me, setMe] = useState<Me | null>(null);
  const [authOn, setAuthOn] = useState(false);

  useEffect(() => {
    captureTokenFromHash();
    fetch(`${API_BASE}/auth/me`, { headers: authHeaders() })
      .then((r) => (r.ok ? r.json() : null))
      .then((d: Me | null) => {
        if (!d) return;
        setAuthOn(d.auth_configured);
        if (getToken() && d.tier !== 'anonymous') setMe(d);
        else if (getToken()) clearToken();
      })
      .catch(() => {});
  }, []);

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
      const filters = latestPlanDocUrl ? { plan_doc_url: latestPlanDocUrl } : undefined;
      const response = await fetch(`${API_BASE}/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({ query, history, filters }),
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
            if (ev.type === 'done' && ev.mode === 'PLAN' && ev.created_doc_url) {
              setLatestPlanDocUrl(ev.created_doc_url);
            }
            setMessages((prev) => {
              const msgs = [...prev];
              const last = msgs[msgs.length - 1];
              if (last?.role !== 'agent') return prev;
              if (ev.type === 'mode')  return [...msgs.slice(0, -1), { ...last, mode: ev.mode }];
              if (ev.type === 'token') return [...msgs.slice(0, -1), { ...last, content: last.content + ev.content }];
              if (ev.type === 'done') {
                return [...msgs.slice(0, -1), {
                  ...last,
                  mode: ev.mode,
                  citations: ev.citations ?? [],
                  created_doc_url: ev.created_doc_url,
                  calendar_event_url: ev.calendar_event_url,
                  calendar_event_start_date: ev.calendar_event_start_date,
                  gmail_draft_id: ev.gmail_draft_id,
                  gmail_draft_url: ev.gmail_draft_url,
                  summary: ev.summary,
                }];
              }
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
          <div key={s.label} className="relative group">
            <button
              onClick={() => setInputValue(s.query)}
              disabled={loading}
              className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full text-xs font-semibold border transition-all disabled:opacity-40"
              style={{
                color: s.color,
                background: s.color + '12',
                borderColor: s.color + '40',
                boxShadow: `0 0 12px ${s.color}18`,
              }}
              onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.background = s.color + '22'; (e.currentTarget as HTMLButtonElement).style.boxShadow = `0 0 18px ${s.color}30`; }}
              onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.background = s.color + '12'; (e.currentTarget as HTMLButtonElement).style.boxShadow = `0 0 12px ${s.color}18`; }}
            >
              <span className="tracking-widest text-[10px]">{s.label}</span>
              <span style={{ color: s.color + 'aa', fontSize: '11px' }}>{s.tip}</span>
            </button>
          </div>
        ))}
      </div>
    </div>
  );

  return (
    <div className="h-screen flex flex-col overflow-hidden" style={{ background: 'var(--bg-0)', fontFamily: 'var(--sans)' }}>
      {(authOn || me) && (
        <div className="fixed top-3 right-4 z-40 flex items-center gap-2 text-xs" style={{ color: 'var(--text-400)' }}>
          {me ? (
            <>
              <span className="px-2.5 py-1 rounded-full border font-semibold" style={{ borderColor: 'var(--accent)', color: 'var(--accent)', background: 'color-mix(in srgb, var(--accent) 10%, transparent)' }}>
                {me.username ?? 'member'} · {me.tier}
              </span>
              <button onClick={() => { clearToken(); setMe(null); }} className="hover:underline">
                Log out
              </button>
            </>
          ) : (
            <a href={`${API_BASE}/auth/login`} className="px-2.5 py-1 rounded-full border transition-colors" style={{ borderColor: 'var(--text-400)' }}>
              Log in with Discord
            </a>
          )}
        </div>
      )}
      <DocPanel
        open={panelMsg !== null}
        onClose={() => setPanelMsg(null)}
        markdown={panelMsg?.content ?? ''}
        docUrl={panelMsg?.created_doc_url}
        query={panelMsg ? (messages.find((m, i) => m.role === 'user' && messages[i + 1] === panelMsg)?.content ?? 'Planning Brief') : ''}
      />

      {isEmpty ? (
        /* Empty state: everything centered together */
        <div className="flex-1 flex flex-col items-center justify-center px-4 pb-8">
          <div className="text-center mb-8">
            <span className="text-5xl mb-5 block diamond-glow" style={{ color: 'var(--accent)' }}>◆</span>
            <h1 className="text-3xl font-semibold mb-2 tracking-tight" style={{
              background: 'linear-gradient(135deg, #a78bfa 0%, #7C3AED 50%, #6d28d9 100%)',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              backgroundClip: 'text',
            }}>
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
              {messages.map((msg, i) => {
                // Hide the empty streaming placeholder — TypingIndicator covers this state
                const isStreamingPlaceholder =
                  loading &&
                  msg.role === 'agent' &&
                  (msg as { content: string }).content === '' &&
                  i === messages.length - 1;
                if (isStreamingPlaceholder) return null;
                const isActiveStream = loading && i === messages.length - 1 && msg.role === 'agent';
                return (
                  <MessageBubble
                    key={i}
                    message={msg}
                    streaming={isActiveStream}
                    onOpenBrief={
                      msg.role === 'agent' && msg.mode === 'PLAN' && !isActiveStream
                        ? () => setPanelMsg(msg as AgentMessage)
                        : undefined
                    }
                  />
                );
              })}
              {loading && (messages[messages.length - 1]?.role !== 'agent' || (messages[messages.length - 1] as { content: string }).content === '') && (
                <TypingIndicator />
              )}
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
