const MODES = [
  {
    label: 'RECALL',
    color: 'recall',
    tip: 'What happened, what was decided',
  },
  {
    label: 'ANALYZE',
    color: 'analyze',
    tip: 'Trends, comparisons, growth over time',
  },
  {
    label: 'PLAN',
    color: 'plan',
    tip: 'Draft a doc, plan an event — creates a Google Doc',
  },
] as const;

export default function ModeSelector() {
  return (
    <div className="mode-legend">
      {MODES.map((m) => (
        <span key={m.label} className={`mode-chip mode-chip--${m.color}`} title={m.tip}>
          {m.label}
          <span className="mode-chip__tip">{m.tip}</span>
        </span>
      ))}
    </div>
  );
}
