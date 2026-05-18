import React, { useState } from "react";
import AppShell, { PageHeader, SectionLabel } from "@/components/AppShell";
import { useAuth } from "@/lib/auth";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { Download, Bug, CheckCircle2 } from "lucide-react";
import { toast } from "sonner";

export default function SettingsPage() {
  const { user } = useAuth();
  const [exporting, setExporting] = useState(false);

  const exportDebug = async () => {
    setExporting(true);
    try {
      const { data } = await api.get("/debug/export");
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `relayd-debug-${new Date().toISOString().slice(0, 10)}.json`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success("Debug snapshot downloaded");
    } catch (e) {
      toast.error("Export failed: " + (e.response?.data?.detail || e.message));
    } finally {
      setExporting(false);
    }
  };

  return (
    <AppShell>
      <PageHeader title="Settings"
        description="Account information and system configuration."
        testId="settings-header"
      />

      <div className="max-w-xl space-y-4">
        <Card className="rounded-md border border-border p-6">
          <SectionLabel>Account</SectionLabel>
          <div className="grid grid-cols-[140px_1fr] gap-y-3 text-sm">
            <div className="text-muted-foreground">Email</div><div className="font-mono">{user?.email}</div>
            <div className="text-muted-foreground">Name</div><div>{user?.name}</div>
            <div className="text-muted-foreground">Role</div><div><Badge variant="outline">{user?.role}</Badge></div>
            <div className="text-muted-foreground">ID</div><div className="font-mono text-xs text-muted-foreground">{user?.id}</div>
          </div>
        </Card>

        <Card className="rounded-md border border-border p-6">
          <SectionLabel>Debug & Support</SectionLabel>
          <p className="text-sm text-muted-foreground mb-4 leading-relaxed">
            Export a sanitized JSON snapshot of your current Relayd configuration — domains, relays, mailboxes, aliases, delivery stats, and environment flags.
            API keys and passwords are <strong>automatically redacted</strong>. Share this file when reporting a bug.
          </p>
          <div className="flex flex-col gap-2 text-xs text-muted-foreground mb-5">
            <div className="flex items-center gap-2"><CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" /> Includes domain DNS check results and scores</div>
            <div className="flex items-center gap-2"><CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" /> Includes relay types, routing rules, and quota usage</div>
            <div className="flex items-center gap-2"><CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" /> Includes recent delivery log metadata (no email content)</div>
            <div className="flex items-center gap-2"><CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" /> API keys and passwords are masked with ****</div>
          </div>
          <Button onClick={exportDebug} disabled={exporting} variant="outline" className="gap-2">
            {exporting ? <><Bug className="h-4 w-4 animate-pulse" /> Generating…</> : <><Download className="h-4 w-4" /> Export Debug Snapshot</>}
          </Button>
        </Card>

        <Card className="rounded-md border border-border p-6">
          <SectionLabel>Roadmap</SectionLabel>
          <ul className="text-sm space-y-2 text-muted-foreground">
            <li>• Self-hosted IMAP inbox storage (Dovecot / Stalwart integration)</li>
            <li>• Webhook events on send / bounce / open</li>
            <li>• Reputation monitoring & blacklist checks</li>
            <li>• Per-mailbox send quotas</li>
          </ul>
        </Card>
      </div>
    </AppShell>
  );
}
