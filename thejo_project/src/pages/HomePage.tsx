import { Link } from 'react-router-dom';
import {
  CalendarX,
  ChevronRight,
  Coins,
  Headphones,
  Image as ImageIcon,
  Plus,
  type LucideIcon,
} from 'lucide-react';
import { AppShell } from '../components/command-center/AppShell';

interface AgentCard {
  id: string;
  title: string;
  description: string;
  Icon: LucideIcon;
  tone: 'pink' | 'blue' | 'green' | 'purple';
  to?: string;
}

const agents: AgentCard[] = [
  {
    id: 'reservation',
    title: '예약판매 이탈 방지',
    description: '예약 고객 이탈 위험을 분석하고 선제적으로 대응합니다.',
    Icon: CalendarX,
    tone: 'pink',
  },
  {
    id: 'more',
    title: '더 줘',
    description: '손실 위험을 막고 누적 수익 기회를 알려드립니다.',
    Icon: Coins,
    tone: 'blue',
    to: '/agents/more',
  },
  {
    id: 'aftercare',
    title: '사후관리',
    description: '개통 후 고객 관리를 자동화하고 만족도를 높입니다.',
    Icon: Headphones,
    tone: 'green',
  },
  {
    id: 'studio',
    title: '통하길 스튜디오',
    description: '행사에 맞는 홍보 포스터를 손쉽게 제작합니다.',
    Icon: ImageIcon,
    tone: 'purple',
  },
];

function AgentCardBody({ agent }: { agent: AgentCard }) {
  const { Icon } = agent;
  return (
    <>
      <span className={`agent-icon tone-${agent.tone}`} aria-hidden="true">
        <Icon size={26} />
      </span>
      <span className="agent-card-body">
        <span className="badge badge-success">운영 중</span>
        <span className="agent-card-title" style={{ display: 'block' }}>
          {agent.title}
        </span>
        <span className="agent-card-desc" style={{ display: 'block' }}>
          {agent.description}
        </span>
      </span>
      <ChevronRight size={20} className="agent-card-arrow" aria-hidden="true" />
    </>
  );
}

export function HomePage() {
  return (
    <AppShell breadcrumb={['Command Center', '홈']}>
      <div className="page-head">
        <div>
          <h1 className="page-title">Command Center</h1>
          <p className="page-description">통신유통 업무를 돕는 AI 에이전트</p>
        </div>
      </div>

      <div className="home-grid">
        {agents.map((agent) =>
          agent.to ? (
            <Link key={agent.id} to={agent.to} className="agent-card">
              <AgentCardBody agent={agent} />
            </Link>
          ) : (
            <div key={agent.id} className="agent-card">
              <AgentCardBody agent={agent} />
            </div>
          ),
        )}

        <div className="agent-card-add">
          <span className="agent-card-add-icon" aria-hidden="true">
            <Plus size={20} />
          </span>
          <p className="agent-card-add-title">새 에이전트 추가</p>
          <p>
            더 많은 AI 에이전트로
            <br />
            업무의 가능성을 넓혀보세요.
          </p>
        </div>
      </div>
    </AppShell>
  );
}
