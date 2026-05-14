import React from "react";
import AppShell, { PageHeader } from "@/components/AppShell";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export default function DocsPage() {
  return (
    <AppShell>
      <PageHeader 
        title="Documentation" 
        description="Learn how to integrate with Relayd and use the API." 
        testId="docs-header"
      />

      <div className="max-w-4xl space-y-12 pb-16">
        
        {/* Application Overview */}
        <section>
          <h2 className="text-2xl font-semibold tracking-tight mb-4">Application Overview</h2>
          <div className="space-y-4 text-muted-foreground leading-relaxed text-sm">
            <p>
              Relayd is a self-hostable email orchestration platform designed to simplify managing multiple domains, 
              mailboxes, outbound relays, and inbound routing.
            </p>
            <p>
              <strong>Outbound (Sending):</strong> Relayd uses background workers to send emails. You can configure multiple 
              Relay Providers (like Resend or generic SMTP). If the primary provider fails, Relayd automatically falls back to the next one based on priority.
            </p>
            <p>
              <strong>Inbound (Receiving):</strong> Relayd runs a native SMTP listener on port 25. 
              Any email sent to your verified domains will be accepted, parsed, and stored. You can view these directly in the Inbound dashboard.
            </p>
            <p>
              <strong>Routing & Aliases:</strong> You can create Mailboxes (with passwords) or Aliases (forwarding rules). 
              Catch-all aliases (using <code>*</code>) are supported to catch any unrouted mail for a domain.
            </p>
          </div>
        </section>

        {/* API Authentication */}
        <section>
          <h2 className="text-2xl font-semibold tracking-tight mb-4">API Authentication</h2>
          <Card className="p-6 border border-border">
            <p className="text-sm text-muted-foreground mb-4">
              To interact with the API programmatically, you must use an API Key. You can generate these in the 
              <strong> API Tokens</strong> dashboard.
            </p>
            <div className="bg-muted/50 p-4 rounded-md border border-border font-mono text-xs overflow-x-auto">
              <div>Authorization: Bearer re_YOUR_API_KEY_HERE</div>
            </div>
            <p className="text-sm text-muted-foreground mt-4">
              All API routes are prefixed with <code>/api</code>.
            </p>
          </Card>
        </section>

        {/* Endpoints Documentation */}
        <section className="space-y-6">
          <h2 className="text-2xl font-semibold tracking-tight mb-4">Endpoints</h2>

          {/* Send Email */}
          <Card className="p-0 overflow-hidden border border-border">
            <div className="bg-muted/30 px-6 py-4 border-b border-border flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Badge className="bg-blue-500/10 text-blue-500 hover:bg-blue-500/20 border-blue-500/20 shadow-none">POST</Badge>
                <code className="font-semibold text-sm">/api/send/test</code>
              </div>
            </div>
            <div className="p-6 text-sm text-muted-foreground">
              <p className="mb-4">Pushes an email to the background worker queue for delivery.</p>
              <h4 className="font-medium text-foreground mb-2">Request Body (JSON)</h4>
              <pre className="bg-muted/50 p-4 rounded-md border border-border font-mono text-xs overflow-x-auto mb-4">
{`{
  "from_email": "hello@yourdomain.com",
  "to": "user@example.com",
  "subject": "Welcome!",
  "text": "Hello world.",
  "html": "<p>Hello world.</p>"
}`}
              </pre>
              <h4 className="font-medium text-foreground mb-2">Response</h4>
              <pre className="bg-muted/50 p-4 rounded-md border border-border font-mono text-xs overflow-x-auto">
{`{
  "task_id": "uuid-string",
  "status": "queued"
}`}
              </pre>
            </div>
          </Card>

          {/* List Domains */}
          <Card className="p-0 overflow-hidden border border-border">
            <div className="bg-muted/30 px-6 py-4 border-b border-border flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Badge className="bg-emerald-500/10 text-emerald-500 hover:bg-emerald-500/20 border-emerald-500/20 shadow-none">GET</Badge>
                <code className="font-semibold text-sm">/api/domains</code>
              </div>
            </div>
            <div className="p-6 text-sm text-muted-foreground">
              <p className="mb-4">Retrieves all domains configured in your account.</p>
              <h4 className="font-medium text-foreground mb-2">Response</h4>
              <pre className="bg-muted/50 p-4 rounded-md border border-border font-mono text-xs overflow-x-auto">
{`[
  {
    "id": "...",
    "name": "example.com",
    "verified": true,
    "score": 100
  }
]`}
              </pre>
            </div>
          </Card>

          {/* List Inbound Messages */}
          <Card className="p-0 overflow-hidden border border-border">
            <div className="bg-muted/30 px-6 py-4 border-b border-border flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Badge className="bg-emerald-500/10 text-emerald-500 hover:bg-emerald-500/20 border-emerald-500/20 shadow-none">GET</Badge>
                <code className="font-semibold text-sm">/api/inbound/messages</code>
              </div>
            </div>
            <div className="p-6 text-sm text-muted-foreground">
              <p className="mb-4">Retrieves recently received inbound emails.</p>
              <h4 className="font-medium text-foreground mb-2">Query Parameters</h4>
              <ul className="list-disc pl-5 mb-4 space-y-1">
                <li><code>limit</code> (optional) - Number of messages to return (default 50).</li>
              </ul>
              <h4 className="font-medium text-foreground mb-2">Response</h4>
              <pre className="bg-muted/50 p-4 rounded-md border border-border font-mono text-xs overflow-x-auto">
{`[
  {
    "id": "...",
    "from": "sender@gmail.com",
    "to": "you@yourdomain.com",
    "subject": "Re: Invoice",
    "body_text": "...",
    "created_at": "..."
  }
]`}
              </pre>
            </div>
          </Card>

        </section>
      </div>
    </AppShell>
  );
}
