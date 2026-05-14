import React, { useState, useEffect } from "react";
import AppShell, { PageHeader } from "@/components/AppShell";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { BookOpen, Code, Server, Shield, Globe, Terminal, Link as LinkIcon, Search } from "lucide-react";

const DOCS_SECTIONS = [
  { id: "overview", icon: BookOpen, title: "Overview & Architecture" },
  { id: "deployment", icon: Server, title: "Deployment (Coolify)" },
  { id: "domains", icon: Globe, title: "Domains & Cloudflare" },
  { id: "identities", icon: Shield, title: "Mailboxes & Aliases" },
  { id: "orchestration", icon: Terminal, title: "Relay Orchestration" },
  { id: "api", icon: Code, title: "API Reference" },
];

export default function DocsPage() {
  const [activeId, setActiveId] = useState("overview");

  useEffect(() => {
    const hash = window.location.hash.replace("#", "");
    if (DOCS_SECTIONS.find(s => s.id === hash)) {
      setActiveId(hash);
    }
  }, []);

  const setPage = (id) => {
    setActiveId(id);
    window.location.hash = id;
  };

  const Content = () => {
    switch(activeId) {
      case "overview": return <OverviewDoc setPage={setPage} />;
      case "deployment": return <DeploymentDoc />;
      case "domains": return <DomainsDoc />;
      case "identities": return <IdentitiesDoc />;
      case "orchestration": return <OrchestrationDoc />;
      case "api": return <ApiDoc />;
      default: return <OverviewDoc setPage={setPage} />;
    }
  };

  return (
    <AppShell fullWidth>
      <div className="flex h-[calc(100vh-60px)]">
        {/* Docs Sidebar */}
        <div className="w-64 border-r border-border bg-muted/10 p-4 overflow-y-auto hidden md:block shrink-0">
          <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-4 px-2">Knowledge Base</div>
          <nav className="space-y-1">
            {DOCS_SECTIONS.map(s => (
              <button
                key={s.id}
                onClick={() => setPage(s.id)}
                className={`w-full flex items-center gap-3 px-3 py-2 text-sm rounded-md transition-colors ${
                  activeId === s.id ? "bg-primary/10 text-primary font-medium" : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
                }`}
              >
                <s.icon className="h-4 w-4" />
                {s.title}
              </button>
            ))}
          </nav>
        </div>

        {/* Docs Content */}
        <div className="flex-1 overflow-y-auto">
          {/* Mobile Doc Nav */}
          <div className="md:hidden sticky top-0 z-30 bg-background/80 backdrop-blur-md border-b border-border px-4 py-3">
            <div className="flex items-center gap-2 overflow-x-auto no-scrollbar pb-1">
              {DOCS_SECTIONS.map(s => (
                <button
                  key={s.id}
                  onClick={() => setPage(s.id)}
                  className={`whitespace-nowrap px-3 py-1.5 text-xs rounded-full border transition-colors ${
                    activeId === s.id 
                      ? "bg-primary border-primary text-primary-foreground font-medium" 
                      : "border-border text-muted-foreground hover:text-foreground"
                  }`}
                >
                  {s.title}
                </button>
              ))}
            </div>
          </div>

          <div className="max-w-3xl mx-auto px-4 md:px-6 py-8 md:py-10 pb-20">
            <Content />
          </div>
        </div>
      </div>
    </AppShell>
  );
}

function OverviewDoc({ setPage }) {
  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-300">
      <h1 className="text-3xl font-bold tracking-tight">Relayd Documentation</h1>
      <p className="text-muted-foreground text-lg">
        Relayd is a self-hostable email orchestration platform designed to replace fragmented Postfix instances with a unified "Datadog for Email" architecture.
      </p>
      
      <div className="grid sm:grid-cols-2 gap-4 mt-8">
        <Card className="p-5 border-border hover:border-foreground/30 transition-colors cursor-pointer" onClick={() => setPage("orchestration")}>
          <Terminal className="h-5 w-5 mb-3 text-blue-500" />
          <h3 className="font-semibold mb-1">Hybrid Orchestration</h3>
          <p className="text-sm text-muted-foreground">Learn how to load-balance Resend, SES, and Brevo dynamically.</p>
        </Card>
        <Card className="p-5 border-border hover:border-foreground/30 transition-colors cursor-pointer" onClick={() => setPage("deployment")}>
          <Server className="h-5 w-5 mb-3 text-emerald-500" />
          <h3 className="font-semibold mb-1">1-Click Deployment</h3>
          <p className="text-sm text-muted-foreground">Deploy Relayd to Coolify or Dokploy in seconds.</p>
        </Card>
      </div>

      <h2 className="text-2xl font-semibold mt-10 mb-4 border-b border-border pb-2">Core Concepts</h2>
      <div className="space-y-4 text-sm text-muted-foreground leading-relaxed">
        <p><strong>Outbound (Sending):</strong> Relayd acts as an API gateway. You send an email to Relayd, and the background worker routes it to the optimal provider based on weight, priority, and quota limits.</p>
        <p><strong>Inbound (Receiving):</strong> Relayd runs a native SMTP listener (Port 25). It captures inbound emails for your domains and displays them in a secure, multi-tenant Webmail UI.</p>
      </div>
    </div>
  );
}

function DeploymentDoc() {
  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-300">
      <h1 className="text-3xl font-bold tracking-tight">Deployment</h1>
      <p className="text-muted-foreground text-lg">Relayd runs natively in Docker and is fully compatible with modern PaaS platforms.</p>
      
      <h2 className="text-xl font-semibold mt-8 mb-2">Deploying via Coolify</h2>
      <Card className="p-6 border-border">
        <ol className="list-decimal pl-5 space-y-3 text-sm text-muted-foreground">
          <li>Create a new <strong>Docker Compose</strong> resource in Coolify.</li>
          <li>Point it to the Relayd GitHub repository.</li>
          <li>Coolify will automatically read the <code>docker-compose.yml</code> file at the root of the project.</li>
          <li>Set the following Environment Variables in the Coolify UI:
            <ul className="list-disc pl-5 mt-2 space-y-1 font-mono text-xs text-foreground">
              <li>JWT_SECRET=your_secure_random_string</li>
              <li>DOMAIN=relayd.yourdomain.com</li>
            </ul>
          </li>
          <li>Click Deploy. Coolify's Traefik proxy will route port 80 to the Frontend, while port 25 remains exposed for inbound mail.</li>
        </ol>
      </Card>
    </div>
  );
}

function DomainsDoc() {
  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-300">
      <h1 className="text-3xl font-bold tracking-tight">Domains & DNS Sync</h1>
      <p className="text-muted-foreground text-lg">How to verify your domains and automatically provision DNS records.</p>
      
      <h2 className="text-xl font-semibold mt-8 mb-2">Cloudflare Auto-Sync</h2>
      <p className="text-sm text-muted-foreground">
        Instead of manually copying MX, SPF, DKIM, and DMARC records, Relayd can push them directly to your Cloudflare zone.
      </p>
      <Card className="p-6 border-border bg-muted/10 mt-4">
        <ol className="list-decimal pl-5 space-y-3 text-sm text-foreground">
          <li>Add your Domain in the Relayd dashboard.</li>
          <li>Click the <strong>Auto-Sync (Cloudflare)</strong> button on the domain details page.</li>
          <li>Provide a Cloudflare API Token. The token must have <strong>Zone.DNS (Edit)</strong> permissions.</li>
          <li>Relayd automatically resolves the Zone ID and pushes exactly what is needed.</li>
        </ol>
      </Card>
      <div className="text-xs text-muted-foreground mt-2 flex items-center gap-2">
        <Shield className="h-4 w-4" /> Security Note: Your Cloudflare Token is never saved to the database. It is only held in memory for the duration of the sync.
      </div>
    </div>
  );
}

function IdentitiesDoc() {
  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-300">
      <h1 className="text-3xl font-bold tracking-tight">Mailboxes & Aliases</h1>
      <p className="text-muted-foreground text-lg">Routing inbound emails efficiently while maintaining tenant privacy.</p>
      
      <h2 className="text-xl font-semibold mt-8 mb-2">Catch-All Aliases</h2>
      <p className="text-sm text-muted-foreground">
        To receive all emails sent to a domain, create an alias with the address <code>*@yourdomain.com</code>. 
        You can route this alias to your personal email address.
      </p>

      <h2 className="text-xl font-semibold mt-8 mb-2">Multi-Tenant Webmail Privacy</h2>
      <p className="text-sm text-muted-foreground mb-4">
        By default, the Admin Unified Inbox shows all inbound emails. However, if you create a <strong>Dedicated Mailbox</strong> (which has its own password login), 
        any emails sent to that address are explicitly stripped from the Admin's view. 
      </p>
      <Card className="p-4 border-l-4 border-l-blue-500 bg-blue-500/5 text-sm">
        This guarantees privacy. You can host mailboxes for clients or employees on your Relayd instance without their private emails cluttering your Admin view.
      </Card>

      <h2 className="text-xl font-semibold mt-8 mb-2">IMAP / External Client Support</h2>
      <p className="text-sm text-muted-foreground mb-4">
        Relayd supports bridging to third-party IMAP servers like <strong>Stalwart</strong> or <strong>Dovecot</strong> for full external client support (Apple Mail, Outlook, Thunderbird).
      </p>
      <Card className="p-6 border-border">
        <ul className="list-disc pl-5 space-y-2 text-sm text-foreground">
          <li><strong>Authentication:</strong> Configure your IMAP server to use HTTP directory authentication against <code>/api/auth/imap</code>. Relayd natively verifies the mailbox passwords.</li>
          <li><strong>Inbound Routing:</strong> When Relayd receives an email on Port 25 destined for a dedicated mailbox, it will automatically forward a copy to the internal IMAP container on Port 2525.</li>
        </ul>
      </Card>
    </div>
  );
}

function OrchestrationDoc() {
  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-300">
      <h1 className="text-3xl font-bold tracking-tight">Relay Orchestration</h1>
      <p className="text-muted-foreground text-lg">Configuring the traffic engineering engine.</p>
      
      <h2 className="text-xl font-semibold mt-8 mb-2">Priority Failover</h2>
      <p className="text-sm text-muted-foreground">
        Relays are executed in order of Priority (Lower number runs first). If your primary provider (Priority 10) encounters an error (like a 429 Rate Limit), 
        the worker will gracefully fall back to the next provider (Priority 20).
      </p>

      <h2 className="text-xl font-semibold mt-8 mb-2">Load Balancing (Weights)</h2>
      <p className="text-sm text-muted-foreground mb-4">
        If two or more Relays share the exact same Priority, Relayd will load balance between them using their configured <strong>Weight</strong>.
      </p>
      <Card className="p-4 border border-border bg-muted/20">
        <div className="font-mono text-sm mb-2 text-foreground font-semibold">Example Setup: 70/30 Split</div>
        <ul className="list-disc pl-5 text-sm text-muted-foreground space-y-1">
          <li><strong>Amazon SES:</strong> Priority 10, Weight 70</li>
          <li><strong>Resend:</strong> Priority 10, Weight 30</li>
        </ul>
        <div className="mt-3 text-xs text-muted-foreground border-t border-border pt-3">
          The engine uses a weighted random distribution algorithm to route 70% of traffic to SES and 30% to Resend. Perfect for warming up new IPs!
        </div>
      </Card>

      <h2 className="text-xl font-semibold mt-8 mb-2">Rate-Limit Throttling</h2>
      <p className="text-sm text-muted-foreground">
        If a provider has a configured <strong>Daily Quota</strong>, Relayd will proactively throttle it as it approaches the limit.
        At 75% usage, its load-balance weight is halved. At 90% usage, it is heavily throttled to preserve quota for high-priority matching emails.
      </p>
    </div>
  );
}

function ApiDoc() {
  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-300">
      <h1 className="text-3xl font-bold tracking-tight">API Reference</h1>
      <p className="text-muted-foreground text-lg">Interact with Relayd programmatically from your applications.</p>
      
      <Card className="p-6 border border-border mt-6">
        <h3 className="font-semibold mb-2 flex items-center gap-2"><KeyRound className="h-4 w-4" /> Authentication</h3>
        <p className="text-sm text-muted-foreground mb-4">
          Generate an API Key from the Dashboard. All API requests must include the token in the Authorization header.
        </p>
        <div className="bg-black/50 p-4 rounded-md border border-border font-mono text-xs overflow-x-auto text-emerald-400">
          Authorization: Bearer re_YOUR_API_KEY_HERE
        </div>
      </Card>

      <h2 className="text-xl font-semibold mt-10 mb-4">Core Endpoints</h2>
      
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
          <pre className="bg-black/50 text-gray-300 p-4 rounded-md border border-border font-mono text-xs overflow-x-auto mb-4">
{`{
  "from_email": "hello@yourdomain.com",
  "to": "user@example.com",
  "subject": "Welcome!",
  "text": "Hello world.",
  "html": "<p>Hello world.</p>"
}`}
          </pre>
        </div>
      </Card>

      {/* List Inbound */}
      <Card className="p-0 overflow-hidden border border-border mt-4">
        <div className="bg-muted/30 px-6 py-4 border-b border-border flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Badge className="bg-emerald-500/10 text-emerald-500 hover:bg-emerald-500/20 border-emerald-500/20 shadow-none">GET</Badge>
            <code className="font-semibold text-sm">/api/inbound/messages</code>
          </div>
        </div>
        <div className="p-6 text-sm text-muted-foreground">
          <p className="mb-4">Retrieves recently received inbound emails. Protected by tenant privacy rules.</p>
        </div>
      </Card>
    </div>
  );
}

// Ensure KeyRound is imported
import { KeyRound } from "lucide-react";
