import { AppShell } from '../components/command-center/AppShell';

interface PlaceholderPageProps {
  title: string;
  description: string;
}

/** 사이드바 링크가 끊기지 않도록 두는 임시 페이지. */
export function PlaceholderPage({ title, description }: PlaceholderPageProps) {
  return (
    <AppShell breadcrumb={['Command Center', title]}>
      <div className="page-head">
        <div>
          <h1 className="page-title">{title}</h1>
          <p className="page-description">{description}</p>
        </div>
      </div>
      <div className="card placeholder-card">준비 중인 화면입니다.</div>
    </AppShell>
  );
}
