import { useState, type ReactNode } from 'react';
import { AppSidebar } from './AppSidebar';
import { TopHeader } from './TopHeader';

interface AppShellProps {
  breadcrumb?: string[];
  children: ReactNode;
}

/** 모든 Command Center 페이지가 공유하는 레이아웃. */
export function AppShell({ breadcrumb, children }: AppShellProps) {
  const [isSidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="app-shell">
      <AppSidebar isOpen={isSidebarOpen} onClose={() => setSidebarOpen(false)} />

      <div className="app-main">
        <TopHeader breadcrumb={breadcrumb} onOpenSidebar={() => setSidebarOpen(true)} />
        <main className="app-content">
          <div className="app-content-inner">{children}</div>
        </main>
      </div>
    </div>
  );
}
