import { useState } from 'react';
import type { Citation } from '../types';

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
            <li key={c.file_id + i} className="citation">
              <div className="citation__title">
                {c.drive_url ? (
                  <a href={c.drive_url} target="_blank" rel="noopener noreferrer">
                    {c.title}
                  </a>
                ) : (
                  c.title
                )}
              </div>
              <div className="citation__meta">
                {c.date && <span className="citation__date">{formatDate(c.date)}</span>}
                <span className={scoreClass(c.relevance_score)}>
                  {scoreLabel(c.relevance_score)} relevance
                </span>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
