import { useRef, useState, type ReactNode } from 'react';
import { CopyIcon, CheckIcon } from 'lucide-react';
import type { Message } from '../types';
import CitationCard from './CitationCard';

function renderInline(text: string): (ReactNode | string)[] {
  const parts = text.split(/(\*\*[^*]+\*\*)/);
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={i}>{part.slice(2, -2)}</strong>;
    }
    return part;
  });
}

function isTableSeparator(line: string): boolean {
  const t = line.trim();
  // A separator row starts with | and contains only pipes, dashes, colons, spaces
  return t.startsWith('|') && !/[a-zA-Z0-9]/.test(t);
}

function parseTableBlock(lines: string[]) {
  const rows = lines
    .filter((l) => l.trim().startsWith('|') && !isTableSeparator(l))
    .map((l) =>
      l.trim().replace(/^\||\|$/g, '').split('|').map((cell) => cell.trim())
    );
  if (rows.length < 2) return null;
  const [header, ...body] = rows;
  return { header, body };
}

function renderContent(text: string) {
  const normalized = text.replace(/\\n/g, '\n');
  // Collapse blank lines between table rows so Gemini-style tables stay as one block
  const tableFixed = normalized.replace(/(\|[^\n]*)\n\n+(?=\|)/g, '$1\n');
  const blocks = tableFixed.split(/\n\n+/);
  return blocks.map((block, i) => {
    const lines = block.split('\n');

    if (block.startsWith('## ')) {
      return <h3 key={i} className="msg__heading">{renderInline(block.slice(3))}</h3>;
    }
    if (block.startsWith('# ')) {
      return <h3 key={i} className="msg__heading">{renderInline(block.slice(2))}</h3>;
    }

    // Markdown table: any block where most lines start with |
    const tableLines = lines.filter((l) => l.trim().startsWith('|'));
    if (tableLines.length >= 2 && tableLines.length >= lines.length - 1) {
      const parsed = parseTableBlock(lines);
      if (parsed) {
        return (
          <div key={i} className="msg__table-wrap">
            <table className="msg__table">
              <thead>
                <tr>
                  {parsed.header.map((cell, j) => (
                    <th key={j}>{renderInline(cell)}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {parsed.body.map((row, j) => (
                  <tr key={j}>
                    {row.map((cell, k) => (
                      <td key={k}>{renderInline(cell)}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
      }
    }

    const isList = lines.every((l) => l.match(/^[-*]\s/));
    if (isList) {
      return (
        <ul key={i} className="msg__list">
          {lines.map((l, j) => (
            <li key={j}>{renderInline(l.replace(/^[-*]\s/, ''))}</li>
          ))}
        </ul>
      );
    }

    const hasBullets = lines.some((l) => l.match(/^[-*]\s/));
    if (hasBullets) {
      return (
        <div key={i}>
          {lines.map((l, j) => {
            if (l.match(/^[-*]\s/)) {
              return <ul key={j} className="msg__list"><li>{renderInline(l.replace(/^[-*]\s/, ''))}</li></ul>;
            }
            return <p key={j} className="msg__para">{renderInline(l)}</p>;
          })}
        </div>
      );
    }

    return (
      <p key={i} className="msg__para">
        {lines.map((line, j) => (
          <span key={j}>
            {renderInline(line)}
            {j < lines.length - 1 && <br />}
          </span>
        ))}
      </p>
    );
  });
}

const MODE_LABELS: Record<string, string> = {
  CHAT: 'CHAT',
  RECALL: 'RECALL',
  ANALYZE: 'ANALYZE',
  PLAN: 'PLAN',
};

interface Props {
  message: Message;
  streaming?: boolean;
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

export default function MessageBubble({ message, streaming = false }: Props) {
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

  return (
    <div className="bubble bubble--agent">
      <div className="bubble__header">
        <span className={`mode-badge mode-badge--${message.mode.toLowerCase()}`}>
          {MODE_LABELS[message.mode]}
        </span>
      </div>
      <div className="bubble__body bubble__body--agent" ref={bodyRef}>
        {message.mode === 'PLAN'
          ? renderContent(message.summary ?? message.content)
          : renderContent(message.content)
        }
      </div>
      {message.mode === 'PLAN' && (message.created_doc_url || message.calendar_event_url || message.gmail_draft_url) && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginTop: '10px' }}>
          {message.created_doc_url && (
            <a className="doc-link" href={message.created_doc_url} target="_blank" rel="noopener noreferrer">
              <span className="doc-link__icon">📄</span>
              Open Planning Brief
            </a>
          )}
          {message.calendar_event_url && (
            <a className="doc-link" href={message.calendar_event_url} target="_blank" rel="noopener noreferrer"
              style={{ background: '#eff6ff', borderColor: '#bfdbfe', color: '#1d4ed8' }}>
              <span className="doc-link__icon">📅</span>
              View Calendar Event{message.calendar_event_start_date ? ` — ${message.calendar_event_start_date}` : ''}
            </a>
          )}
          {message.gmail_draft_url && (
            <a className="doc-link" href={message.gmail_draft_url} target="_blank" rel="noopener noreferrer"
              style={{ background: '#faf5ff', borderColor: '#e9d5ff', color: '#7c3aed' }}>
              <span className="doc-link__icon">✉️</span>
              Review Email Draft
            </a>
          )}
        </div>
      )}
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: '6px', marginTop: '10px' }}>
        {message.citations.length > 0 && <CitationCard citations={message.citations} />}
        {!streaming && <CopyButton getTextFn={() => bodyRef.current?.innerText ?? message.content} />}
      </div>
    </div>
  );
}
