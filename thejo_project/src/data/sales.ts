import type { MonthlySalesSummary, SaleRecord } from '../types/incentive';

/**
 * 2026년 9월 판매일보. 사장님이 별도로 입력하지 않고 기존 데이터를 그대로 읽어온다.
 *
 * - TX-202609-018: 개통 후 30일 만에 요금제 변경 → 환수 위험
 * - TX-202609-022: 고객 혜택이 커서 최소 마진 미달
 */
export const currentMonthSales: SaleRecord[] = [
  {
    id: 'TX-202609-003',
    soldAt: '2026-09-02',
    maskedCustomer: '김O은',
    device: 'Galaxy S26',
    planName: '5G 프리미엄',
    baseIncentive: 480_000,
    customerBenefit: 150_000,
    storeCost: 30_000,
    planChangedAfterDays: null,
  },
  {
    id: 'TX-202609-007',
    soldAt: '2026-09-04',
    maskedCustomer: '박O준',
    device: 'iPhone 18',
    planName: '5G 시그니처',
    baseIncentive: 520_000,
    customerBenefit: 180_000,
    storeCost: 30_000,
    planChangedAfterDays: null,
  },
  {
    id: 'TX-202609-011',
    soldAt: '2026-09-08',
    maskedCustomer: '이O수',
    device: 'Galaxy S26 Ultra',
    planName: '5G 프리미엄',
    baseIncentive: 500_000,
    customerBenefit: 170_000,
    storeCost: 30_000,
    planChangedAfterDays: null,
  },
  {
    id: 'TX-202609-014',
    soldAt: '2026-09-11',
    maskedCustomer: '최O아',
    device: 'Galaxy A56',
    planName: '5G 슬림',
    baseIncentive: 450_000,
    customerBenefit: 140_000,
    storeCost: 25_000,
    planChangedAfterDays: null,
  },
  {
    id: 'TX-202609-018',
    soldAt: '2026-09-15',
    maskedCustomer: '정O현',
    device: 'iPhone 18 Pro',
    planName: '5G 시그니처',
    baseIncentive: 530_000,
    customerBenefit: 190_000,
    storeCost: 30_000,
    planChangedAfterDays: 30,
  },
  {
    id: 'TX-202609-021',
    soldAt: '2026-09-18',
    maskedCustomer: '한O빈',
    device: 'Galaxy Z Flip 7',
    planName: '5G 프리미엄',
    baseIncentive: 470_000,
    customerBenefit: 150_000,
    storeCost: 25_000,
    planChangedAfterDays: null,
  },
  {
    id: 'TX-202609-022',
    soldAt: '2026-09-19',
    maskedCustomer: '오O석',
    device: 'Galaxy A56',
    planName: '5G 슬림',
    baseIncentive: 380_000,
    customerBenefit: 340_000,
    storeCost: 40_000,
    planChangedAfterDays: null,
  },
  {
    id: 'TX-202609-025',
    soldAt: '2026-09-22',
    maskedCustomer: '윤O지',
    device: 'iPhone 18',
    planName: '5G 프리미엄',
    baseIncentive: 510_000,
    customerBenefit: 175_000,
    storeCost: 30_000,
    planChangedAfterDays: null,
  },
  {
    id: 'TX-202609-028',
    soldAt: '2026-09-25',
    maskedCustomer: '강O우',
    device: 'Galaxy S26',
    planName: '5G 시그니처',
    baseIncentive: 490_000,
    customerBenefit: 160_000,
    storeCost: 30_000,
    planChangedAfterDays: null,
  },
];

/** 전월 대비 증감 표시에 사용. */
export const monthlySalesHistory: MonthlySalesSummary[] = [
  { month: '2026-07', salesCount: 6 },
  { month: '2026-08', salesCount: 7 },
];

export const currentMonth = '2026-09';
export const currentMonthLabel = '2026년 9월';
