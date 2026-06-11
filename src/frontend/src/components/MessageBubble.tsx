import { useRef, useState } from 'react';
import { CopyIcon, CheckIcon } from 'lucide-react';
import type { Message } from '../types';
import CitationCard from './CitationCard';
import { renderContent } from '../utils/renderMarkdown';

const MODE_LABELS: Record<string, string> = {
  CHAT: 'CHAT',
  RECALL: 'RECALL',
  ANALYZE: 'ANALYZE',
  PLAN: 'PLAN',
};

interface Props {
  message: Message;
  streaming?: boolean;
  onOpenBrief?: () => void;
}

function CopyButton({ getTextFn }: { getTextFn: () => string }) {
  const [copied, setCopied] = useState(false);
  function handleCopy() {
    navigator.clipboard.writeText(getTextFn()).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }
  return (
    <button className="copy-btn" onClick={handleCopy} title="Copy to clipboard">
      {copied ? <CheckIcon size={14} /> : <CopyIcon size={14} />}
    </button>
  );
}

export default function MessageBubble({ message, streaming = false, onOpenBrief }: Props) {
  const bodyRef = useRef<HTMLDivElement>(null);

  if (message.role === 'user') {
    return (
      <div className="bubble bubble--user">
        <div className="bubble__body">{message.content}</div>
      </div>
    );
  }

  if (message.role === 'error') {
    return (
      <div className="bubble bubble--error">
        <div className="bubble__body">{message.content}</div>
      </div>
    );
  }

  const isPlan = message.mode === 'PLAN';

  return (
    <div className="bubble bubble--agent">
      <div className="bubble__header">
        <span className={`mode-badge mode-badge--${message.mode.toLowerCase()}`}>
          {MODE_LABELS[message.mode]}
        </span>
      </div>

      <div className="bubble__body bubble__body--agent" ref={bodyRef}>
        {isPlan ? (
          streaming ? (
            <span className="plan-brief-generating">Drafting your planning brief…</span>
          ) : (
            <div className="plan-brief-card">
              <p className="plan-brief-card__summary">
                {message.summary ?? 'Your planning brief is ready.'}
              </p>
              {onOpenBrief && (
                <button className="plan-brief-card__open" onClick={onOpenBrief}>
                  <span>Open Brief</span>
                  <span>→</span>
                </button>
              )}
            </div>
          )
        ) : (
          renderContent(message.content)
        )}
      </div>

      {isPlan && !streaming && (message.created_doc_url || message.calendar_event_url || message.gmail_draft_url) && (
        <div className="artifact-row">
          {message.created_doc_url && (
            <a className="doc-link" href={message.created_doc_url} target="_blank" rel="noopener noreferrer">
              <span className="doc-link__icon">📄</span>
              Google Drive
            </a>
          )}
          {message.calendar_event_url && (
            <a className="doc-link" href={message.calendar_event_url} target="_blank" rel="noopener noreferrer"
              style={{ background: 'rgba(96,165,250,0.08)', borderColor: 'rgba(96,165,250,0.25)', color: '#93c5fd', boxShadow: '0 0 12px rgba(96,165,250,0.1)' }}>
              <span className="doc-link__icon">📅</span>
              Calendar Event
            </a>
          )}
          {message.gmail_draft_url && (
            <div className="doc-link" style={{ background: 'rgba(251,191,36,0.08)', borderColor: 'rgba(251,191,36,0.25)', color: '#fcd34d', cursor: 'default', boxShadow: '0 0 12px rgba(251,191,36,0.08)' }}>
              <span className="doc-link__icon">✉️</span>
              Email Sent
            </div>
          )}
        </div>
      )}

      <div style={{ display: 'flex', alignItems: 'flex-start', gap: '6px', marginTop: '10px' }}>
        {message.citations.length > 0 && <CitationCard citations={message.citations} />}
        {!streaming && !isPlan && (
          <CopyButton getTextFn={() => bodyRef.current?.innerText ?? message.content} />
        )}
      </div>
    </div>
  );
}
