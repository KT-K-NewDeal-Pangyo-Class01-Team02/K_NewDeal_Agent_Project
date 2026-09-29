const wonFormatter = new Intl.NumberFormat('ko-KR');

/** 1100000 → "1,100,000원" */
export function formatWon(value: number): string {
  return `${wonFormatter.format(Math.round(value))}원`;
}

/** 부호를 항상 붙인다. -200000 → "-200,000원", 0 → "0원" */
export function formatSignedWon(value: number): string {
  if (value === 0) return '0원';
  const sign = value > 0 ? '+' : '-';
  return `${sign}${wonFormatter.format(Math.abs(Math.round(value)))}원`;
}

export function formatCount(value: number): string {
  return `${wonFormatter.format(value)}건`;
}

export function formatSignedCount(value: number): string {
  if (value === 0) return '변동 없음';
  const sign = value > 0 ? '+' : '-';
  return `${sign}${Math.abs(value)}건`;
}

/** "2026-09-15" → "2026.09.15" */
export function formatDate(isoDate: string): string {
  const [year, month, day] = isoDate.split('-');
  return `${year}.${month}.${day}`;
}

/** 분석 시각 표시용. "2026년 9월 29일 14:05" */
export function formatAnalyzedAt(isoDateTime: string): string {
  const date = new Date(isoDateTime);
  if (Number.isNaN(date.getTime())) return '-';
  const hours = String(date.getHours()).padStart(2, '0');
  const minutes = String(date.getMinutes()).padStart(2, '0');
  return `${date.getFullYear()}년 ${date.getMonth() + 1}월 ${date.getDate()}일 ${hours}:${minutes}`;
}
