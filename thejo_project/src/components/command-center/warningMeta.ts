import { CircleAlert, Scale, TriangleAlert, type LucideIcon } from 'lucide-react';
import type { WarningCategory, WarningSeverity } from '../../types/incentive';

/** 위험도 표시에 필요한 라벨과 배지 클래스. */
export const severityMeta: Record<
  WarningSeverity,
  { label: string; badgeClass: string; toneClass: string }
> = {
  critical: { label: '긴급', badgeClass: 'badge badge-danger', toneClass: 'sev-critical' },
  warning: { label: '주의', badgeClass: 'badge badge-caution', toneClass: 'sev-warning' },
  info: { label: '확인', badgeClass: 'badge badge-info', toneClass: 'sev-info' },
};

/** 위험 유형별 아이콘과 사람이 읽는 이름. */
export const categoryMeta: Record<WarningCategory, { label: string; Icon: LucideIcon }> = {
  clawback: { label: '환수 위험', Icon: TriangleAlert },
  'settlement-gap': { label: '정산 금액 불일치', Icon: Scale },
  'low-margin': { label: '최소 마진 미달', Icon: CircleAlert },
};
