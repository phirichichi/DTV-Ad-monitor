//App.tsx
import React from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import LoginPage from "./pages/LoginPage";
import DashboardPage from "./pages/DashboardPage";
import MonitoringPage from "./pages/MonitoringPage";
import ReportsPage from "./pages/ReportsPage";
import AdvertiserAnalyticsPage from "./pages/AdvertiserAnalyticsPage";

// ✅ NEW extracted pages
import UsersPage from "./pages/UsersPage";
import ChannelsPage from "./pages/ChannelsPage";
import AdLibraryPage from "./pages/AdLibraryPage";
import OperationsHealthPage from "./pages/OperationsHealthPage";

import { AuthProvider } from "./features/auth/AuthContext";
import { ProtectedRoute } from "./components/common/ProtectedRoute";

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>

          {/* Public */}
          <Route path="/login" element={<LoginPage />} />

          {/* Dashboard */}
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute allowedRoles={["admin", "operator", "client"]}>
                <DashboardPage />
              </ProtectedRoute>
            }
          />

          {/* Users */}
          <Route
            path="/users"
            element={
              <ProtectedRoute allowedRoles={["admin"]}>
                <UsersPage />
              </ProtectedRoute>
            }
          />

          {/* Channels */}
          <Route
            path="/channels"
            element={
              <ProtectedRoute allowedRoles={["admin"]}>
                <ChannelsPage />
              </ProtectedRoute>
            }
          />

          {/* Advertisers */}
          <Route
            path="/advertisers"
            element={
              <ProtectedRoute allowedRoles={["admin", "client"]}>
                <AdvertiserAnalyticsPage />
              </ProtectedRoute>
            }
          />

          {/* Ad Library */}
          <Route
            path="/ads"
            element={
              <ProtectedRoute allowedRoles={["admin", "operator"]}>
                <AdLibraryPage />
              </ProtectedRoute>
            }
          />

          {/* Monitoring */}
          <Route
            path="/monitoring"
            element={
              <ProtectedRoute allowedRoles={["admin", "operator"]}>
                <MonitoringPage />
              </ProtectedRoute>
            }
          />

          {/* Reports */}
          <Route
            path="/reports"
            element={
              <ProtectedRoute allowedRoles={["admin", "operator", "client"]}>
                <ReportsPage />
              </ProtectedRoute>
            }
          />

          {/* Operations Health */}
          <Route
            path="/operations-health"
            element={
              <ProtectedRoute allowedRoles={["admin", "operator"]}>
                <OperationsHealthPage />
              </ProtectedRoute>
            }
          />

          {/* Default redirect */}
          <Route path="*" element={<Navigate to="/dashboard" replace />} />

        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;