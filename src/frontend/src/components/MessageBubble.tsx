import { useRef, useState } from 'react';
import { CopyIcon, CheckIcon, FileTextIcon, CalendarIcon, MailCheckIcon, ExternalLinkIcon } from 'lucide-react';
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
              <span className="plan-brief-card__label">Planning Brief</span>
              <p className="plan-brief-card__summary">
                {message.summary ?? 'Your planning brief is ready.'}
              </p>
              {onOpenBrief && (
                <button className="plan-brief-card__open" onClick={onOpenBrief}>
                  <FileTextIcon size={13} />
                  <span>Open Brief</span>
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
              <span className="doc-link__dot" style={{ background: '#4ade80' }} />
              <span className="doc-link__icon"><FileTextIcon size={12} /></span>
              Google Doc
              <ExternalLinkIcon size={10} style={{ opacity: 0.4, marginLeft: 2 }} />
            </a>
          )}
          {message.calendar_event_url && (
            <a className="doc-link" href={message.calendar_event_url} target="_blank" rel="noopener noreferrer">
              <span className="doc-link__dot" style={{ background: '#4ade80' }} />
              <span className="doc-link__icon"><CalendarIcon size={12} /></span>
              Calendar
              <ExternalLinkIcon size={10} style={{ opacity: 0.4, marginLeft: 2 }} />
            </a>
          )}
          {message.gmail_draft_url && (
            <a className="doc-link" href={message.gmail_draft_url} target="_blank" rel="noopener noreferrer">
              <span className="doc-link__dot" style={{ background: '#4ade80' }} />
              <span className="doc-link__icon"><MailCheckIcon size={12} /></span>
              Email Sent
              <ExternalLinkIcon size={10} style={{ opacity: 0.4, marginLeft: 2 }} />
            </a>
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
