# Command Center

통신유통 업무를 돕는 AI 에이전트 대시보드입니다.

- **스택**: Vite 8 + React 19 + TypeScript + React Router 7 + lucide-react
- **스타일링**: CSS 커스텀 프로퍼티 기반 디자인 토큰 (`src/styles/tokens.css`). UI 프레임워크 없음.

## 실행

```bash
npm install
npm run dev      # http://localhost:5173
npm run build    # 타입 검사(tsc -b) + 프로덕션 빌드
npm run verify   # 계산 로직이 정책 명세와 일치하는지 검증
```

> `npm run lint`(oxlint)는 네이티브 바이너리가 Windows Application Control 정책에
> 차단될 수 있습니다. 타입 검사는 `npm run build`에 포함되어 있습니다.

## 화면

| 경로 | 설명 |
| --- | --- |
| `/` | 에이전트 카드 목록. '더 줘' 카드 전체가 클릭 영역입니다. |
| `/agents/more` | **'더 줘' Agent 대시보드** |
| `/agents`, `/activity`, `/settings` | 사이드바 링크용 임시 화면 |

## '더 줘' Agent

판매점 사장님이 아무것도 입력하지 않아도, 기존 **판매일보**와 **정산 데이터**를
자동으로 분석해 두 가지를 보여줍니다.

1. **오늘의 Warning** — 환수 위험, 정산 금액 불일치, 최소 마진 미달
2. **놓치기 쉬운 수익 기회** — 월간 누적 판매량과 구간형 인센티브 분석

### 자동 분석 흐름

```
판매정책과 환수 조건 불러오기
→ 기존 판매일보 데이터 불러오기
→ 실제 정산 데이터 불러오기
→ 필수 데이터 검증
→ 거래별 예상 인센티브와 마진 계산
→ 월간 판매량과 마진 누적
→ 예상 정산액과 실제 정산액 비교
→ 환수·정산 불일치·최소 마진 미달 탐지
→ 다음 인센티브 구간과 추가 수익 계산
→ Warning과 수익 기회를 우선순위별로 표시
```

페이지에 들어오면 바로 실행되고, `자동 분석 다시 실행` 버튼으로 재실행합니다.

## 금액 계산은 LLM이 아니라 코드가 합니다

모든 금액은 `src/services/`의 **순수 TypeScript 함수**가 계산합니다.
AI Agent는 계산 결과의 우선순위를 정하고 쉬운 문장으로 설명하는 역할만 합니다.

```
거래별 예상 마진 = 예상 인센티브 - 고객 혜택 - 매장 부담 비용 - 예상 환수 금액
정산 차액        = 실제 정산액 - 예상 인센티브
```

### 구간형 인센티브 정책

`src/data/policies.ts`의 데모 정책은 `retroactive`(소급 적용) 방식입니다.

```
1~9건:   건당 100,000원
10~19건: 건당 200,000원
10건 달성 시 당월 전체 거래에 소급 적용
```

`calculateVolumeIncentive()`는 세 가지 정책 타입을 모두 지원하므로,
`rewardType`만 바꾸면 다른 정산 방식으로 전환됩니다.

| `TierRewardType` | 의미 | 10건 달성 시 |
| --- | --- | --- |
| `retroactive` | 당월 전체 거래에 소급 적용 | 2,000,000원 |
| `incremental` | 구간 달성 이후 거래부터 단가 상승 | 1,100,000원 |
| `lump-sum` | 목표 달성 시 일괄 보너스 | 기본 단가 + 보너스 |

## 폴더 구조

```
src/
  pages/
    HomePage.tsx            Command Center 홈 (에이전트 카드)
    MoreAgentPage.tsx       '더 줘' 대시보드
    PlaceholderPage.tsx
  components/command-center/
    AppShell.tsx            사이드바 + 헤더 + 콘텐츠 셸
    AppSidebar.tsx
    TopHeader.tsx
    SummaryCard.tsx         핵심 요약 카드
    WarningList.tsx         오늘의 Warning
    WarningDetail.tsx       Warning 상세 모달
    DealDetail.tsx          이상 없는 거래의 상세 모달
    ProfitOpportunity.tsx   누적 수익 기회
    SettlementTable.tsx     최근 정산 비교
    CalculationList.tsx     계산 근거 목록
    Modal.tsx               ESC로 닫히는 공용 모달
    Skeletons.tsx
    warningMeta.ts          위험도/유형 표시 메타
  data/
    policies.ts             판매정책, 환수 조건, 최소 마진 기준
    sales.ts                판매일보 mock data
    settlements.ts          실제 정산 mock data
  services/
    incentiveCalculator.ts  인센티브·마진·정산 차액 계산
    warningDetector.ts      손실 위험 탐지
    opportunityDetector.ts  누적 수익 기회 탐지
    analysis.ts             자동 분석 파이프라인
  hooks/
    usePersistentSet.ts     조치 완료 상태를 localStorage에 보존
  types/
    incentive.ts
  utils/
    format.ts
  styles/
    tokens.css / layout.css / components.css
scripts/
  verify.ts                 계산 결과 검증
```

## 상태 보존

`조치 완료`와 `기회 확인 완료`는 `localStorage`에 저장되어 새로고침 후에도
유지됩니다. 저장소가 차단된 환경에서도 화면은 정상 동작합니다.

- `thejo.more-agent.resolved-warnings.v1`
- `thejo.more-agent.acknowledged.v1`

## 이번 구현 범위 밖

고객 내방 시 단말·요금제 직접 입력, 고객별 맞춤 혜택 추천, 해지 가능성 예측,
실제 통신사 API 연동, 실고객 개인정보 저장, LLM 금액 계산, 로그인·권한·결제,
정책 PDF 자동 해석은 포함하지 않습니다.
