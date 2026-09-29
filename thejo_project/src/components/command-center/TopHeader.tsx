import { Bell, ChevronDown, CircleUser, Menu, Search } from 'lucide-react';

interface TopHeaderProps {
  /** Breadcrumb 조각. 마지막 항목이 현재 페이지로 강조된다. */
  breadcrumb?: string[];
  onOpenSidebar: () => void;
}

export function TopHeader({ breadcrumb = [], onOpenSidebar }: TopHeaderProps) {
  return (
    <header className="top-header">
      <button
        type="button"
        className="icon-button sidebar-toggle"
        aria-label="메뉴 열기"
        onClick={onOpenSidebar}
      >
        <Menu size={20} aria-hidden="true" />
      </button>

      <nav className="top-header-breadcrumb" aria-label="현재 위치">
        {breadcrumb.map((crumb, index) => {
          const isLast = index === breadcrumb.length - 1;
          return (
            <span key={crumb}>
              {index > 0 && <span aria-hidden="true"> / </span>}
              {isLast ? <strong>{crumb}</strong> : crumb}
            </span>
          );
        })}
      </nav>

      <div className="header-search">
        <Search size={17} aria-hidden="true" />
        <input type="search" placeholder="무엇을 도와드릴까요?" aria-label="검색" />
      </div>

      <button type="button" className="icon-button" aria-label="알림 보기">
        <Bell size={20} aria-hidden="true" />
      </button>

      <button type="button" className="header-user">
        <span className="header-avatar" aria-hidden="true">
          <CircleUser size={22} />
        </span>
        <span className="header-user-name">김지현 매니저</span>
        <ChevronDown size={16} aria-hidden="true" color="#98a2b3" />
      </button>
    </header>
  );
}
