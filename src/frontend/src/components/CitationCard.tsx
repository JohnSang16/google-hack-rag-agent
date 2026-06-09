import { useState } from 'react';
import type { Citation, DiscordMessage } from '../types';

function scoreLabel(score: number): string {
  if (score >= 8) return 'High';
  if (score >= 5) return 'Medium';
  return 'Low';
}

function scoreClass(score: number): string {
  if (score >= 8) return 'rel rel--high';
  if (score >= 5) return 'rel rel--med';
  return 'rel rel--low';
}

function formatDate(date: string | null): string {
  if (!date) return '';
  try {
    return new Date(date).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  } catch {
    return date;
  }
}

function DiscordMessageList({ messages }: { messages: DiscordMessage[] }) {
  return (
    <ul className="discord-messages">
      {messages.map((m, i) => (
        <li key={i} className="discord-message">
          <span className="discord-message__time">{m.time}</span>
          <span className="discord-message__author">{m.author}</span>
          <span className="discord-message__content">{m.content}</span>
        </li>
      ))}
    </ul>
  );
}

function CitationItem({ c }: { c: Citation }) {
  const [messagesOpen, setMessagesOpen] = useState(false);
  const isDiscord = c.source_type === 'discord';
  const linkUrl = isDiscord ? c.discord_url : c.drive_url;
  const linkLabel = isDiscord ? 'Open in Discord' : 'Open in Drive';
  const hasMessages = isDiscord && c.messages && c.messages.length > 0;

  return (
    <li className="citation">
      <div className="citation__title">
        {linkUrl ? (
          <a href={linkUrl} target="_blank" rel="noopener noreferrer">
            {c.title}
          </a>
        ) : (
          c.title
        )}
        {linkUrl && (
          <span className="citation__link-label">{linkLabel}</span>
        )}
      </div>
      <div className="citation__meta">
        {c.date && <span className="citation__date">{formatDate(c.date)}</span>}
        <span className={scoreClass(c.relevance_score)}>
          {scoreLabel(c.relevance_score)} relevance
        </span>
      </div>
      {hasMessages && (
        <div className="citation__messages-section">
          <button
            className="citation__messages-toggle"
            onClick={() => setMessagesOpen((o) => !o)}
            aria-expanded={messagesOpen}
          >
            {messagesOpen ? '▾' : '▸'} {messagesOpen ? 'Hide' : 'Show'} messages ({c.messages!.length})
          </button>
          {messagesOpen && <DiscordMessageList messages={c.messages!} />}
        </div>
      )}
    </li>
  );
}

interface Props {
  citations: Citation[];
}

export default function CitationCard({ citations }: Props) {
  const [open, setOpen] = useState(false);

  if (citations.length === 0) return null;

  return (
    <div className="citations">
      <button
        className="citations__toggle"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
      >
        <span className="citations__icon">{open ? '▾' : '▸'}</span>
        Sources ({citations.length})
      </button>

      {open && (
        <ul className="citations__list">
          {citations.map((c, i) => (
            <CitationItem key={c.file_id + i} c={c} />
          ))}
        </ul>
      )}
    </div>
  );
}
