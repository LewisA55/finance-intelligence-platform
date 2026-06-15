export type StatusTone = 'favourable' | 'adverse' | 'on-plan' | 'warning' | 'neutral';

const LABELS: Record<StatusTone, string> = {
  favourable: 'Favourable',
  adverse: 'Adverse',
  'on-plan': 'On Plan',
  warning: 'Review',
  neutral: '—',
};

interface StatusPillProps {
  tone: StatusTone;
  label?: string;
}

export function StatusPill({ tone, label }: StatusPillProps) {
  return (
    <span className={`status-pill ${tone}`}>
      <span className="dot" />
      {label ?? LABELS[tone]}
    </span>
  );
}
