import { NavLink } from 'react-router-dom';
import { Bot, Clock, Coins, House, Settings, X } from 'lucide-react';

interface AppSidebarProps {
  isOpen: boolean;
  onClose: () => void;
}

const navItems = [
  { to: '/', label: '홈', Icon: House },
  { to: '/agents', label: '에이전트', Icon: Bot },
  { to: '/activity', label: '활동 내역', Icon: Clock },
  { to: '/settings', label: '설정', Icon: Settings },
  { to: '/agents/more', label: '더 줘', Icon: Coins },
];

export function AppSidebar({ isOpen, onClose }: AppSidebarProps) {
  return (
    <>
      {isOpen && (
        <button
          type="button"
          className="sidebar-scrim"
          aria-label="메뉴 닫기"
          onClick={onClose}
        />
      )}

      <nav
        className={`sidebar${isOpen ? ' is-open' : ''}`}
        aria-label="주요 메뉴"
      >
        <div className="sidebar-logo">Command Center</div>

        <button type="button" className="sidebar-close" aria-label="메뉴 닫기" onClick={onClose}>
          <X size={20} aria-hidden="true" />
        </button>

        <div className="sidebar-nav">
          {navItems.map(({ to, label, Icon }) => (
            <NavLink
              key={to}
              to={to}
              end
              onClick={onClose}
              className={({ isActive }) => `sidebar-link${isActive ? ' is-active' : ''}`}
            >
              <Icon size={18} aria-hidden="true" />
              <span>{label}</span>
            </NavLink>
          ))}
        </div>

        <div className="sidebar-footer">
          <div className="sidebar-note">
            AI와 함께
            <br />더 나은 유통의 내일을
            <br />
            만듭니다.
            <span className="sidebar-note-bar" aria-hidden="true" />
          </div>
        </div>
      </nav>
    </>
  );
}
