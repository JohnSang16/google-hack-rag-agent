import { useEffect } from 'react';
import { XIcon, DownloadIcon, ExternalLinkIcon } from 'lucide-react';
import { renderContent } from '../utils/renderMarkdown';

interface DocPanelProps {
  open: boolean;
  onClose: () => void;
  markdown: string;
  docUrl?: string;
  query: string;
}

export default function DocPanel({ open, onClose, markdown, docUrl, query }: DocPanelProps) {
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose();
    }
    if (open) document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  function handleDownload() {
    const blob = new Blob([markdown], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${query.slice(0, 48).replace(/[^a-z0-9]+/gi, '-').toLowerCase()}.md`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <>
      {/* Backdrop */}
      <div
        className="doc-panel__backdrop"
        style={{ opacity: open ? 1 : 0, pointerEvents: open ? 'auto' : 'none' }}
        onClick={onClose}
      />

      {/* Panel */}
      <div className="doc-panel" style={{ transform: open ? 'translateX(0)' : 'translateX(100%)' }}>
        <div className="doc-panel__header">
          <span className="doc-panel__title">Planning Brief</span>
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
            {docUrl && (
              <a
                href={docUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="doc-panel__btn"
                title="Open in Drive"
              >
                <ExternalLinkIcon size={14} />
                <span>Drive</span>
              </a>
            )}
            <button className="doc-panel__btn" onClick={handleDownload} title="Download .md">
              <DownloadIcon size={14} />
              <span>Download</span>
            </button>
            <button className="doc-panel__close" onClick={onClose} title="Close">
              <XIcon size={16} />
            </button>
          </div>
        </div>

        <div className="doc-panel__body">
          <p className="doc-panel__query">{query}</p>
          <div className="doc-panel__content">
            {renderContent(markdown)}
          </div>
        </div>
      </div>
    </>
  );
}
