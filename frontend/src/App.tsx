// App.tsx — Root application with routing
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import type { ReactElement } from 'react';
import AuthPage from './pages/AuthPage';
import ChatPage from './pages/ChatPage';

function PrivateRoute({ children }: { children: ReactElement }) {
  const token = localStorage.getItem('token');
  return token ? children : <Navigate to="/" replace />;
}

export default function App() {
  return (
    <BrowserRouter>
      <>
        {/* Animated background */}
        <div className="app-bg" />

        <Routes>
          <Route path="/" element={<AuthPage />} />
          <Route
            path="/chat"
            element={
              <PrivateRoute>
                <ChatPage />
              </PrivateRoute>
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </>
    </BrowserRouter>
  );
}
