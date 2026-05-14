import React, { useEffect, useState } from "react";
import AppShell, { PageHeader, SectionLabel } from "@/components/AppShell";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Globe, Inbox, ArrowRightLeft, Send, CheckCircle2, AlertTriangle } from "lucide-react";
import { Link } from "react-router-dom";

const Stat = ({ label, value, icon: Icon, testId }) => (
  <Card className="rounded-md border border-border bg-card p-5 transition-colors hover:border-foreground/30" data-testid={testId}>
    <div className="flex items-center justify-between">
      <div className="text-xs uppercase tracking-[0.18em] font-semibold text-muted-foreground">{label}</div>
      <Icon className="h-4 w-4 text-muted-foreground" />
    </div>
    <div className="mt-3 text-3xl font-semibold tracking-tight font-mono">{value}</div>
  </Card>
);

export default function DashboardPage() {
  const [stats, setStats] = useState(null);

  useEffect(() => {
    api.get("/stats").then((r) => setStats(r.data)).catch(() => setStats({}));
  }, []);

  return (
    <AppShell>
      <PageHeader
        title="Overview"
        description="Snapshot of your email orchestration: domains, mailboxes, relays, and recent delivery health."
        testId="dashboard-header"
      />

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Stat label="Domains" value={stats?.domains ?? "—"} icon={Globe} testId="stat-domains" />
        <Stat label="Mailboxes" value={stats?.mailboxes ?? "—"} icon={Inbox} testId="stat-mailboxes" />
        <Stat label="Aliases" value={stats?.aliases ?? "—"} icon={ArrowRightLeft} testId="stat-aliases" />
        <Stat label="Relays" value={stats?.relays ?? "—"} icon={Send} testId="stat-relays" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mt-4">
        <Card className="rounded-md border border-border p-5 col-span-2">
          <div className="flex items-center justify-between mb-4">
            <SectionLabel>Delivery health</SectionLabel>
            <Link to="/logs" className="text-xs text-muted-foreground hover:text-foreground" data-testid="view-all-logs-link">View all →</Link>
          </div>
          <div className="grid grid-cols-3 gap-4">
            <div>
              <div className="text-xs text-muted-foreground">Sent</div>
              <div className="text-2xl font-mono font-semibold mt-1" data-testid="stat-sent">{stats?.sent ?? 0}</div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">Failed</div>
              <div className="text-2xl font-mono font-semibold mt-1 text-destructive" data-testid="stat-failed">{stats?.failed ?? 0}</div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">Total</div>
              <div className="text-2xl font-mono font-semibold mt-1" data-testid="stat-total">{stats?.total_logs ?? 0}</div>
            </div>
          </div>
          <div className="mt-6 border-t border-border pt-4">
            <SectionLabel>Recent</SectionLabel>
            {(!stats?.recent_logs || stats.recent_logs.length === 0) && (
              <div className="text-sm text-muted-foreground py-6 text-center border border-dashed border-border rounded-sm">
                No delivery activity yet. Send a test email from the Relays page.
              </div>
            )}
            {stats?.recent_logs?.map((l) => (
              <div key={l.id} className="flex items-center justify-between py-2 border-b border-border last:border-0 text-sm">
                <div className="font-mono text-xs truncate flex-1">{l.subject}</div>
                <div className="text-muted-foreground text-xs font-mono mx-3 truncate">{l.to}</div>
                <Badge variant="outline" className={l.status === "sent" ? "text-emerald-500 border-emerald-500/40" : "text-destructive border-destructive/40"}>
                  {l.status}
                </Badge>
              </div>
            ))}
          </div>
        </Card>

        <Card className="rounded-md border border-border p-5">
          <SectionLabel>Verification</SectionLabel>
          <div className="space-y-3">
            <div className="flex items-center gap-2 text-sm">
              <CheckCircle2 className="h-4 w-4 text-emerald-500" />
              <span className="font-mono">{stats?.verified_domains ?? 0}</span>
              <span className="text-muted-foreground">verified domains</span>
            </div>
            <div className="flex items-center gap-2 text-sm">
              <AlertTriangle className="h-4 w-4 text-amber-500" />
              <span className="font-mono">{(stats?.domains ?? 0) - (stats?.verified_domains ?? 0)}</span>
              <span className="text-muted-foreground">pending</span>
            </div>
            <Link to="/deliverability" className="block mt-4 text-xs underline underline-offset-4" data-testid="run-checks-link">
              Run deliverability checks →
            </Link>
          </div>
        </Card>
      </div>
    </AppShell>
  );
}
