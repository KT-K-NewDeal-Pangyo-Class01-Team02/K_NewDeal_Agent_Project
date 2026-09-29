import type { CalculationLine } from '../../types/incentive';

interface CalculationListProps {
  lines: CalculationLine[];
}

/** 계산 근거를 한 줄씩 그대로 보여준다. */
export function CalculationList({ lines }: CalculationListProps) {
  return (
    <ul className="calc-list">
      {lines.map((line) => (
        <li key={line.label}>
          <span className="calc-label">{line.label}</span>
          <span className="calc-expression">{line.expression}</span>
        </li>
      ))}
    </ul>
  );
}
