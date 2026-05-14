import React from "react";
import AppShell, { PageHeader, SectionLabel } from "@/components/AppShell";
import { useAuth } from "@/lib/auth";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export default function SettingsPage() {
  const { user } = useAuth();
  return (
    <AppShell>
      <PageHeader title="Settings"
        description="Your account information. More configuration options (API tokens, webhooks, SMTP listener) coming next."
        testId="settings-header"
      />
      <Card className="rounded-md border border-border p-6 max-w-xl">
        <SectionLabel>Account</SectionLabel>
        <div className="grid grid-cols-[140px_1fr] gap-y-3 text-sm">
          <div className="text-muted-foreground">Email</div><div className="font-mono">{user?.email}</div>
          <div className="text-muted-foreground">Name</div><div>{user?.name}</div>
          <div className="text-muted-foreground">Role</div><div><Badge variant="outline">{user?.role}</Badge></div>
          <div className="text-muted-foreground">ID</div><div className="font-mono text-xs text-muted-foreground">{user?.id}</div>
        </div>
      </Card>

      <Card className="rounded-md border border-border p-6 mt-4 max-w-xl">
        <SectionLabel>Roadmap</SectionLabel>
        <ul className="text-sm space-y-2 text-muted-foreground">
          <li>• Inbound SMTP relay & MX listener</li>
          <li>• Self-hosted IMAP inbox storage</li>
          <li>• Webhook events on send / bounce / open</li>
          <li>• API token management</li>
          <li>• Reputation monitoring & blacklist checks</li>
        </ul>
      </Card>
    </AppShell>
  );
}
