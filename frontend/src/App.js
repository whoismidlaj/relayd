import React from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "@/lib/auth";
import { ThemeProvider } from "@/lib/theme";
import { Toaster } from "@/components/ui/sonner";

import AuthPage from "@/pages/AuthPage";
import DashboardPage from "@/pages/DashboardPage";
import DomainsPage from "@/pages/DomainsPage";
import DomainDetailPage from "@/pages/DomainDetailPage";
import MailboxesPage from "@/pages/MailboxesPage";
import AliasesPage from "@/pages/AliasesPage";
import RelaysPage from "@/pages/RelaysPage";
import LogsPage from "@/pages/LogsPage";
import DeliverabilityPage from "@/pages/DeliverabilityPage";
import SettingsPage from "@/pages/SettingsPage";
import InboundPage from "@/pages/InboundPage";
import WorkerPage from "@/pages/WorkerPage";
import TokensPage from "@/pages/TokensPage";
import DocsPage from "@/pages/DocsPage";

function Protected({ children, requireAdmin }) {
  const { user } = useAuth();
  if (user === null) {
    return (
      <div className="min-h-screen grid place-items-center bg-background text-muted-foreground text-sm">
        Loading…
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace />;
  
  if (requireAdmin && user.role === "mailbox") {
    return <Navigate to="/inbound" replace />;
  }
  
  return children;
}

export default function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<AuthPage mode="login" />} />
            <Route path="/register" element={<AuthPage mode="register" />} />

            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<Protected requireAdmin><DashboardPage /></Protected>} />
            <Route path="/domains" element={<Protected requireAdmin><DomainsPage /></Protected>} />
            <Route path="/domains/:id" element={<Protected requireAdmin><DomainDetailPage /></Protected>} />
            <Route path="/mailboxes" element={<Protected requireAdmin><MailboxesPage /></Protected>} />
            <Route path="/aliases" element={<Protected requireAdmin><AliasesPage /></Protected>} />
            <Route path="/relays" element={<Protected requireAdmin><RelaysPage /></Protected>} />
            <Route path="/worker" element={<Protected requireAdmin><WorkerPage /></Protected>} />
            
            {/* Accessible by Mailbox users */}
            <Route path="/inbound" element={<Protected><InboundPage /></Protected>} />
            
            <Route path="/logs" element={<Protected requireAdmin><LogsPage /></Protected>} />
            <Route path="/deliverability" element={<Protected requireAdmin><DeliverabilityPage /></Protected>} />
            <Route path="/tokens" element={<Protected requireAdmin><TokensPage /></Protected>} />
            <Route path="/docs" element={<Protected requireAdmin><DocsPage /></Protected>} />
            <Route path="/settings" element={<Protected requireAdmin><SettingsPage /></Protected>} />

            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Routes>
          <Toaster richColors closeButton />
        </BrowserRouter>
      </AuthProvider>
    </ThemeProvider>
  );
}
