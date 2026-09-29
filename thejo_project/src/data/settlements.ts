import type { SettlementRecord } from '../types/incentive';

/**
 * 통신사에서 실제로 지급된 정산 내역.
 *
 * - TX-202609-011: 예상 500,000원 대비 300,000원만 지급 → 정산 불일치
 */
export const currentMonthSettlements: SettlementRecord[] = [
  { saleId: 'TX-202609-003', settledAt: '2026-09-25', actualPayout: 480_000, adjustmentNote: null },
  { saleId: 'TX-202609-007', settledAt: '2026-09-25', actualPayout: 520_000, adjustmentNote: null },
  {
    saleId: 'TX-202609-011',
    settledAt: '2026-09-25',
    actualPayout: 300_000,
    adjustmentNote: '정산서상 조정 사유 미기재',
  },
  { saleId: 'TX-202609-014', settledAt: '2026-09-25', actualPayout: 450_000, adjustmentNote: null },
  { saleId: 'TX-202609-018', settledAt: '2026-09-25', actualPayout: 530_000, adjustmentNote: null },
  { saleId: 'TX-202609-021', settledAt: '2026-09-25', actualPayout: 470_000, adjustmentNote: null },
  { saleId: 'TX-202609-022', settledAt: '2026-09-25', actualPayout: 380_000, adjustmentNote: null },
  { saleId: 'TX-202609-025', settledAt: '2026-09-25', actualPayout: 510_000, adjustmentNote: null },
  { saleId: 'TX-202609-028', settledAt: '2026-09-25', actualPayout: 490_000, adjustmentNote: null },
];
