import React, { useEffect, useState } from "react";
import AppShell, { PageHeader, SectionLabel } from "@/components/AppShell";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Globe, Inbox, ArrowRightLeft, Send, CheckCircle2, AlertTriangle, Activity, BarChart3, Zap, MailCheck, MailOpen } from "lucide-react";
import { Link } from "react-router-dom";
import { 
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  BarChart, Bar, LineChart, Line 
} from "recharts";

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

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-4">
        <Card className="rounded-md border border-border bg-card p-5 transition-colors hover:border-foreground/30 flex items-center gap-5" data-testid="stat-sent">
          <div className="h-12 w-12 rounded-full bg-blue-500/10 text-blue-500 flex items-center justify-center shrink-0">
            <MailCheck className="h-5 w-5" />
          </div>
          <div>
            <div className="text-xs uppercase tracking-[0.18em] font-semibold text-muted-foreground">Emails Sent</div>
            <div className="mt-1 text-3xl font-semibold tracking-tight font-mono">{stats?.sent ?? "—"}</div>
            <div className="text-[11px] text-muted-foreground mt-0.5">{stats?.failed ?? 0} failed / bounced</div>
          </div>
        </Card>
        <Card className="rounded-md border border-border bg-card p-5 transition-colors hover:border-foreground/30 flex items-center gap-5" data-testid="stat-received">
          <div className="h-12 w-12 rounded-full bg-emerald-500/10 text-emerald-500 flex items-center justify-center shrink-0">
            <MailOpen className="h-5 w-5" />
          </div>
          <div>
            <div className="text-xs uppercase tracking-[0.18em] font-semibold text-muted-foreground">Emails Received</div>
            <div className="mt-1 text-3xl font-semibold tracking-tight font-mono">{stats?.received ?? "—"}</div>
            <div className="text-[11px] text-muted-foreground mt-0.5">across all mailboxes</div>
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mt-4">
        {/* Main Timeseries Chart */}
        <Card className="rounded-md border border-border p-5 col-span-2">
          <div className="flex items-center justify-between mb-6">
            <SectionLabel>Delivery Volume & Bounces</SectionLabel>
            <Badge variant="outline" className="font-mono text-[10px]">14D ROLLUP</Badge>
          </div>
          <div className="h-[250px] w-full min-w-0 relative">
            <ResponsiveContainer width="100%" height="100%" minHeight={250} debounce={1}>
              {stats?.timeseries ? (
                <AreaChart data={stats.timeseries} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
                  <defs>
                    <linearGradient id="colorSent" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3}/>
                      <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
                    </linearGradient>
                    <linearGradient id="colorBounce" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#ef4444" stopOpacity={0.3}/>
                      <stop offset="95%" stopColor="#ef4444" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#333" vertical={false} />
                  <XAxis dataKey="date" axisLine={false} tickLine={false} tick={{ fontSize: 10, fill: '#888' }} />
                  <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 10, fill: '#888' }} />
                  <Tooltip 
                    contentStyle={{ backgroundColor: '#111', borderColor: '#333', fontSize: '12px' }}
                    itemStyle={{ color: '#fff' }}
                  />
                  <Area type="monotone" dataKey="sent" stroke="#3b82f6" strokeWidth={2} fillOpacity={1} fill="url(#colorSent)" name="Sent" />
                  <Area type="monotone" dataKey="bounces" stroke="#ef4444" strokeWidth={2} fillOpacity={1} fill="url(#colorBounce)" name="Bounces" />
                </AreaChart>
              ) : (
                <div className="h-full flex items-center justify-center text-muted-foreground text-sm">Loading charts...</div>
              )}
            </ResponsiveContainer>
          </div>
        </Card>

        {/* Reputation Gauge & Checks */}
        <Card className="rounded-md border border-border p-5 flex flex-col">
          <SectionLabel>Domain Reputation</SectionLabel>
          <div className="flex-1 flex flex-col items-center justify-center py-6">
            <div className="relative">
              <svg className="w-32 h-32 transform -rotate-90">
                <circle cx="64" cy="64" r="56" stroke="currentColor" strokeWidth="8" fill="transparent" className="text-muted/20" />
                <circle 
                  cx="64" cy="64" r="56" stroke="currentColor" strokeWidth="8" fill="transparent" 
                  strokeDasharray="351.8" strokeDashoffset={351.8 - (351.8 * (stats?.timeseries?.[14]?.reputation || 98)) / 100}
                  className="text-emerald-500 transition-all duration-1000 ease-out" 
                />
              </svg>
              <div className="absolute inset-0 flex flex-col items-center justify-center">
                <span className="text-3xl font-mono font-bold">{stats?.timeseries?.[14]?.reputation || 98}</span>
              </div>
            </div>
            <div className="text-xs text-muted-foreground mt-4 text-center">
              Aggregate score across {stats?.domains || 0} active domains
            </div>
          </div>
          
          <div className="mt-auto border-t border-border pt-4">
            <div className="flex items-center justify-between text-sm mb-2">
              <span className="text-muted-foreground flex items-center gap-2"><CheckCircle2 className="h-4 w-4 text-emerald-500" /> Verified</span>
              <span className="font-mono">{stats?.verified_domains ?? 0}</span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground flex items-center gap-2"><AlertTriangle className="h-4 w-4 text-amber-500" /> Pending</span>
              <span className="font-mono">{(stats?.domains ?? 0) - (stats?.verified_domains ?? 0)}</span>
            </div>
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mt-4">
        {/* Latency Chart */}
        <Card className="rounded-md border border-border p-5">
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-2">
              <Zap className="h-4 w-4 text-amber-500" />
              <SectionLabel>Provider Latency (ms)</SectionLabel>
            </div>
            <div className="text-2xl font-mono">{stats?.timeseries?.[14]?.latency || 0}</div>
          </div>
          <div className="h-[150px] w-full min-w-0 relative">
            <ResponsiveContainer width="100%" height="100%" minHeight={150} debounce={1}>
              {stats?.timeseries ? (
                <LineChart data={stats.timeseries}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#333" vertical={false} />
                  <Tooltip contentStyle={{ backgroundColor: '#111', borderColor: '#333', fontSize: '12px' }} />
                  <Line type="stepAfter" dataKey="latency" stroke="#f59e0b" strokeWidth={2} dot={false} />
                </LineChart>
              ) : (
                <div />
              )}
            </ResponsiveContainer>
          </div>
        </Card>

        {/* Activity Log */}
        <Card className="rounded-md border border-border p-5 flex flex-col">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Activity className="h-4 w-4 text-blue-500" />
              <SectionLabel>Live Orchestration Log</SectionLabel>
            </div>
            <Link to="/logs" className="text-xs text-muted-foreground hover:text-foreground">View all →</Link>
          </div>
          
          <div className="flex-1 space-y-3 overflow-hidden">
            {(!stats?.recent_logs || stats.recent_logs.length === 0) && (
              <div className="text-sm text-muted-foreground h-full flex items-center justify-center border border-dashed border-border rounded-sm">
                No delivery activity yet.
              </div>
            )}
            {stats?.recent_logs?.map((l) => (
              <div key={l.id} className="flex items-center justify-between py-2 border-b border-border last:border-0 text-sm">
                <div className="font-mono text-[11px] truncate w-[100px] text-muted-foreground">{new Date(l.created_at).toLocaleTimeString()}</div>
                <div className="font-mono text-xs truncate flex-1 mx-2">{l.to}</div>
                <Badge variant="outline" className={l.status === "sent" ? "text-emerald-500 border-emerald-500/40 bg-emerald-500/5 text-[10px]" : "text-destructive border-destructive/40 bg-destructive/5 text-[10px]"}>
                  {l.status}
                </Badge>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </AppShell>
  );
}
