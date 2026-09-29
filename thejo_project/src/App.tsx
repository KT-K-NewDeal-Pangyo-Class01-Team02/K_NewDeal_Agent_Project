import { Navigate, Route, Routes } from 'react-router-dom';
import { HomePage } from './pages/HomePage';
import { MoreAgentPage } from './pages/MoreAgentPage';
import { PlaceholderPage } from './pages/PlaceholderPage';

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/agents/more" element={<MoreAgentPage />} />
      <Route
        path="/agents"
        element={
          <PlaceholderPage title="에이전트" description="운영 중인 AI 에이전트를 관리합니다." />
        }
      />
      <Route
        path="/activity"
        element={
          <PlaceholderPage title="활동 내역" description="에이전트가 수행한 작업 기록입니다." />
        }
      />
      <Route
        path="/settings"
        element={<PlaceholderPage title="설정" description="계정과 알림을 설정합니다." />}
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
