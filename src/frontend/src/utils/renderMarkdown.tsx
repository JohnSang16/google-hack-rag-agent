import type { ReactNode } from 'react';

export function renderInline(text: string): (ReactNode | string)[] {
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

export function renderContent(text: string): ReactNode[] {
  const normalized = text.replace(/\\n/g, '\n');
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

    const tableLines = lines.filter((l) => l.trim().startsWith('|'));
    if (tableLines.length >= 2 && tableLines.length >= lines.length - 1) {
      const parsed = parseTableBlock(lines);
      if (parsed) {
        return (
          <div key={i} className="msg__table-wrap">
            <table className="msg__table">
              <thead>
                <tr>{parsed.header.map((cell, j) => <th key={j}>{renderInline(cell)}</th>)}</tr>
              </thead>
              <tbody>
                {parsed.body.map((row, j) => (
                  <tr key={j}>{row.map((cell, k) => <td key={k}>{renderInline(cell)}</td>)}</tr>
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
          {lines.map((l, j) => <li key={j}>{renderInline(l.replace(/^[-*]\s/, ''))}</li>)}
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
          <span key={j}>{renderInline(line)}{j < lines.length - 1 && <br />}</span>
        ))}
      </p>
    );
  });
}
