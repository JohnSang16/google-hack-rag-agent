import type { ReactNode } from 'react';
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

function renderContent(text: string) {
  const blocks = text.split(/\n\n+/);
  return blocks.map((block, i) => {
    const lines = block.split('\n');

    if (block.startsWith('## ')) {
      return <h3 key={i} className="msg__heading">{renderInline(block.slice(3))}</h3>;
    }
    if (block.startsWith('# ')) {
      return <h3 key={i} className="msg__heading">{renderInline(block.slice(2))}</h3>;
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
  RECALL: 'RECALL',
  ANALYZE: 'ANALYZE',
  PLAN: 'PLAN',
};

interface Props {
  message: Message;
}

export default function MessageBubble({ message }: Props) {
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
      <div className="bubble__body bubble__body--agent">
        {renderContent(message.content)}
      </div>
      {message.created_doc_url && (
        <a
          className="doc-link"
          href={message.created_doc_url}
          target="_blank"
          rel="noopener noreferrer"
        >
          <span className="doc-link__icon">📄</span>
          View Google Doc
        </a>
      )}
      {message.citations.length > 0 && (
        <CitationCard citations={message.citations} />
      )}
    </div>
  );
}
