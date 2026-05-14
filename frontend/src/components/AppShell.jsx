import React from "react";
import { NavLink, useNavigate } from "react-router-dom";
import {
  LayoutDashboard, Globe, Inbox, ArrowRightLeft, Send,
  Activity, ScrollText, Settings, LogOut, Mail, KeyRound, BookOpen, Menu, X
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { ThemeToggle } from "@/lib/theme";
import { useAuth } from "@/lib/auth";
import ComposeDialog from "@/components/ComposeDialog";
import { Plus } from "lucide-react";

const NAV_GROUPS = [
  {
    label: "Orchestration",
    items: [
      { to: "/dashboard", label: "Overview", icon: LayoutDashboard, testId: "nav-overview" },
      { to: "/domains", label: "Domains", icon: Globe, testId: "nav-domains" },
      { to: "/relays", label: "Relays", icon: Send, testId: "nav-relays" },
    ]
  },
  {
    label: "Identities",
    items: [
      { to: "/inbound", label: "Inbound (Webmail)", icon: Inbox, testId: "nav-inbound" },
      { to: "/mailboxes", label: "Mailboxes", icon: Mail, testId: "nav-mailboxes" },
      { to: "/aliases", label: "Aliases", icon: ArrowRightLeft, testId: "nav-aliases" },
    ]
  },
  {
    label: "Intelligence",
    items: [
      { to: "/deliverability", label: "Deliverability", icon: Activity, testId: "nav-deliverability" },
      { to: "/logs", label: "Delivery Logs", icon: ScrollText, testId: "nav-logs" },
      { to: "/worker", label: "Worker Queue", icon: Activity, testId: "nav-worker" },
    ]
  },
  {
    label: "Configuration",
    items: [
      { to: "/tokens", label: "API Tokens", icon: KeyRound, testId: "nav-tokens" },
      { to: "/docs", label: "Documentation", icon: BookOpen, testId: "nav-docs" },
      { to: "/settings", label: "Settings", icon: Settings, testId: "nav-settings" },
    ]
  }
];

export default function AppShell({ children, fullWidth = false }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [mobileMenuOpen, setMobileMenuOpen] = React.useState(false);
  const [composeOpen, setComposeOpen] = React.useState(false);

  const handleLogout = async () => {
    await logout();
    navigate("/login");
  };

  const closeMenu = () => setMobileMenuOpen(false);

  return (
    <div className="min-h-screen flex flex-col md:flex-row bg-background text-foreground">
      {/* Mobile Top Bar */}
      <div className="md:hidden flex items-center justify-between h-14 px-4 border-b border-border bg-background sticky top-0 z-40">
        <div className="flex items-center gap-2">
          <div className="h-7 w-7 rounded-sm bg-foreground text-background grid place-items-center">
            <Mail className="h-4 w-4" />
          </div>
          <div className="leading-tight">
            <div className="text-sm font-semibold tracking-tight">Relayd</div>
          </div>
        </div>
        <Button variant="ghost" size="icon" onClick={() => setMobileMenuOpen(true)}>
          <Menu className="h-5 w-5" />
        </Button>
      </div>

      {/* Mobile Overlay */}
      {mobileMenuOpen && (
        <div 
          className="fixed inset-0 bg-background/80 backdrop-blur-sm z-50 md:hidden"
          onClick={closeMenu}
        />
      )}

      {/* Sidebar */}
      <aside className={`
        fixed inset-y-0 left-0 z-50 w-64 md:w-60 bg-background border-r border-border flex flex-col transition-transform duration-200 ease-in-out
        ${mobileMenuOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}
        md:sticky md:top-0 md:h-screen
      `}>
        <div className="px-5 h-14 flex items-center justify-between border-b border-border">
          <div className="flex items-center gap-2">
            <div className="h-7 w-7 rounded-sm bg-foreground text-background grid place-items-center">
              <Mail className="h-4 w-4" />
            </div>
            <div className="leading-tight">
              <div className="text-sm font-semibold tracking-tight">Relayd</div>
              <div className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground hidden md:block">orchestration</div>
            </div>
          </div>
          <Button variant="ghost" size="icon" className="md:hidden h-8 w-8" onClick={closeMenu}>
            <X className="h-4 w-4" />
          </Button>
        </div>

        <div className="px-4 py-4 border-b border-border">
          <Button 
            className="w-full justify-start gap-2 shadow-sm" 
            onClick={() => setComposeOpen(true)}
            data-testid="sidebar-compose-button"
          >
            <Plus className="h-4 w-4" />
            <span className="font-semibold">Compose</span>
          </Button>
        </div>

        <nav className="flex-1 px-3 py-4 space-y-6 overflow-y-auto">
          {NAV_GROUPS.map((group, i) => {
            const filteredItems = group.items.filter(n => user?.role === "mailbox" ? n.to === "/inbound" : true);
            if (filteredItems.length === 0) return null;
            
            return (
              <div key={i}>
                {user?.role !== "mailbox" && (
                  <div className="mb-2 px-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                    {group.label}
                  </div>
                )}
                <div className="space-y-0.5">
                  {filteredItems.map((n) => (
                    <NavLink
                      key={n.to}
                      to={n.to}
                      data-testid={n.testId}
                      onClick={closeMenu}
                      className={({ isActive }) =>
                        `flex items-center gap-2.5 px-2 h-8 rounded-sm text-sm transition-colors ${
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
                </div>
              </div>
            );
          })}
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
      <main className="flex-1 min-w-0 w-full">
        <div className={`${fullWidth ? 'w-full' : 'max-w-[1200px]'} mx-auto px-4 md:px-6 py-6 md:py-8 animate-in-up`}>{children}</div>
      </main>

      <ComposeDialog open={composeOpen} onOpenChange={setComposeOpen} />
    </div>
  );
}

export function PageHeader({ title, description, actions, testId }) {
  return (
    <div className="flex flex-col md:flex-row md:items-start justify-between gap-4 mb-6 md:mb-8" data-testid={testId}>
      <div>
        <h1 className="text-2xl sm:text-3xl md:text-4xl font-semibold tracking-tight">{title}</h1>
        {description && (
          <p className="mt-2 text-sm text-muted-foreground max-w-xl leading-relaxed">{description}</p>
        )}
      </div>
      {actions && <div className="flex items-center gap-2 flex-wrap">{actions}</div>}
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
