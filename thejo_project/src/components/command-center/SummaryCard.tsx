import type { LucideIcon } from 'lucide-react';

export type SummaryTone = 'default' | 'danger' | 'opportunity';

interface SummaryCardProps {
  label: string;
  Icon: LucideIcon;
  value: string;
  hint: string;
  tone?: SummaryTone;
  hintTone?: 'default' | 'positive';
}

const toneClass: Record<SummaryTone, string> = {
  default: '',
  danger: ' is-danger',
  opportunity: ' is-opportunity',
};

/** 한 카드에 하나의 핵심 숫자만 담는다. */
export function SummaryCard({
  label,
  Icon,
  value,
  hint,
  tone = 'default',
  hintTone = 'default',
}: SummaryCardProps) {
  return (
    <section className="card summary-card">
      <div className="summary-card-top">
        <Icon size={17} aria-hidden="true" />
        <span>{label}</span>
      </div>
      <p className={`summary-card-value${toneClass[tone]}`}>{value}</p>
      <p className={`summary-card-hint${hintTone === 'positive' ? ' is-positive' : ''}`}>{hint}</p>
    </section>
  );
}
