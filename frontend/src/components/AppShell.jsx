import React from "react";
import { NavLink, useNavigate } from "react-router-dom";
import {
  LayoutDashboard, Globe, Inbox, ArrowRightLeft, Send,
  Activity, ScrollText, Settings, LogOut, Mail, KeyRound, BookOpen
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { ThemeToggle } from "@/lib/theme";
import { useAuth } from "@/lib/auth";

const NAV = [
  { to: "/dashboard", label: "Overview", icon: LayoutDashboard, testId: "nav-overview" },
  { to: "/domains", label: "Domains", icon: Globe, testId: "nav-domains" },
  { to: "/mailboxes", label: "Mailboxes", icon: Inbox, testId: "nav-mailboxes" },
  { to: "/aliases", label: "Aliases", icon: ArrowRightLeft, testId: "nav-aliases" },
  { to: "/inbound", label: "Inbound", icon: Inbox, testId: "nav-inbound" },
  { to: "/relays", label: "Relays", icon: Send, testId: "nav-relays" },
  { to: "/worker", label: "Worker", icon: Activity, testId: "nav-worker" },
  { to: "/deliverability", label: "Deliverability", icon: Activity, testId: "nav-deliverability" },
  { to: "/logs", label: "Delivery Logs", icon: ScrollText, testId: "nav-logs" },
  { to: "/tokens", label: "API Tokens", icon: KeyRound, testId: "nav-tokens" },
  { to: "/docs", label: "Documentation", icon: BookOpen, testId: "nav-docs" },
  { to: "/settings", label: "Settings", icon: Settings, testId: "nav-settings" },
];

export default function AppShell({ children }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate("/login");
  };

  return (
    <div className="min-h-screen flex bg-background text-foreground">
      {/* Sidebar */}
      <aside className="w-60 shrink-0 border-r border-border h-screen sticky top-0 flex flex-col">
        <div className="px-5 h-14 flex items-center gap-2 border-b border-border">
          <div className="h-7 w-7 rounded-sm bg-foreground text-background grid place-items-center">
            <Mail className="h-4 w-4" />
          </div>
          <div className="leading-tight">
            <div className="text-sm font-semibold tracking-tight">Relayd</div>
            <div className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground">orchestration</div>
          </div>
        </div>

        <nav className="flex-1 px-2 py-3 space-y-0.5 overflow-y-auto">
          {NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              data-testid={n.testId}
              className={({ isActive }) =>
                `flex items-center gap-2.5 px-3 h-9 rounded-sm text-sm transition-colors ${
                  isActive
                    ? "bg-secondary text-foreground font-medium"
                    : "text-muted-foreground hover:text-foreground hover:bg-accent"
                }`
              }
            >
              <n.icon className="h-4 w-4" />
              <span>{n.label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="border-t border-border p-3 flex items-center gap-2">
          <div className="flex-1 min-w-0">
            <div className="text-xs font-medium truncate" data-testid="sidebar-user-email">{user?.email}</div>
            <div className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground">{user?.role}</div>
          </div>
          <ThemeToggle />
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            onClick={handleLogout}
            data-testid="logout-button"
            title="Logout"
          >
            <LogOut className="h-4 w-4" />
          </Button>
        </div>
      </aside>

      {/* Content */}
      <main className="flex-1 min-w-0">
        <div className="max-w-[1200px] mx-auto px-6 py-8 animate-in-up">{children}</div>
      </main>
    </div>
  );
}

export function PageHeader({ title, description, actions, testId }) {
  return (
    <div className="flex items-start justify-between gap-4 mb-8" data-testid={testId}>
      <div>
        <h1 className="text-3xl sm:text-4xl font-semibold tracking-tight">{title}</h1>
        {description && (
          <p className="mt-2 text-sm text-muted-foreground max-w-xl leading-relaxed">{description}</p>
        )}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}

export function SectionLabel({ children }) {
  return (
    <div className="text-xs uppercase tracking-[0.2em] font-semibold text-muted-foreground mb-3">
      {children}
    </div>
  );
}
