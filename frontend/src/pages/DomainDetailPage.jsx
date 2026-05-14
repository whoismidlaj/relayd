import React, { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import AppShell, { PageHeader, SectionLabel } from "@/components/AppShell";
import { api, formatApiError } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Copy, ChevronLeft, RefreshCw, CheckCircle2, XCircle } from "lucide-react";
import { toast } from "sonner";

const KIND_COLOR = {
  MX: "text-blue-500 border-blue-500/40",
  SPF: "text-emerald-500 border-emerald-500/40",
  DKIM: "text-violet-500 border-violet-500/40",
  DMARC: "text-amber-500 border-amber-500/40",
  A: "text-muted-foreground border-border",
};

function RecordCard({ rec }) {
  const copy = (txt, label) => {
    navigator.clipboard.writeText(txt);
    toast.success(`${label} copied`);
  };
  return (
    <Card className="rounded-md border border-border p-5">
      <div className="flex items-center justify-between mb-3">
        <Badge variant="outline" className={KIND_COLOR[rec.kind] || ""}>{rec.kind}</Badge>
        <span className="text-xs text-muted-foreground">TTL {rec.ttl}</span>
      </div>
      <div className="grid sm:grid-cols-[100px_1fr] gap-x-4 gap-y-2 text-sm">
        <div className="text-xs uppercase tracking-wider text-muted-foreground self-center">Name</div>
        <div className="flex items-center gap-2">
          <code className="dns-code flex-1 px-3 py-1.5 bg-muted/40 rounded-sm border border-border">{rec.name}</code>
          <Button size="icon" variant="ghost" className="h-7 w-7" onClick={() => copy(rec.name, "Name")} data-testid={`copy-name-${rec.kind}`}>
            <Copy className="h-3.5 w-3.5" />
          </Button>
        </div>
        <div className="text-xs uppercase tracking-wider text-muted-foreground self-center">Value</div>
        <div className="flex items-start gap-2">
          <code className="dns-code flex-1 px-3 py-1.5 bg-muted/40 rounded-sm border border-border break-all">{rec.value}</code>
          <Button size="icon" variant="ghost" className="h-7 w-7 mt-0.5" onClick={() => copy(rec.value, `${rec.kind} value`)} data-testid={`copy-value-${rec.kind}`}>
            <Copy className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>
      <div className="mt-2 text-xs text-muted-foreground">{rec.description}</div>
    </Card>
  );
}

function CheckRow({ label, ok, detail }) {
  return (
    <div className="flex items-start gap-3 py-3 border-b border-border last:border-0">
      {ok ? <CheckCircle2 className="h-4 w-4 text-emerald-500 mt-0.5 shrink-0" /> : <XCircle className="h-4 w-4 text-destructive mt-0.5 shrink-0" />}
      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium">{label}</div>
        <div className="text-xs text-muted-foreground font-mono break-all">{detail || (ok ? "OK" : "not found")}</div>
      </div>
    </div>
  );
}

export default function DomainDetailPage() {
  const { id } = useParams();
  const [domain, setDomain] = useState(null);
  const [records, setRecords] = useState([]);
  const [checks, setChecks] = useState(null);
  const [verifying, setVerifying] = useState(false);

  const load = async () => {
    try {
      const [d, dns] = await Promise.all([
        api.get(`/domains/${id}`),
        api.get(`/domains/${id}/dns`),
      ]);
      setDomain(d.data);
      setRecords(dns.data.records);
      setChecks(d.data.checks || null);
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail));
    }
  };

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { load(); }, [id]);

  const verify = async () => {
    setVerifying(true);
    try {
      const { data } = await api.post(`/domains/${id}/verify`);
      setChecks(data.checks);
      toast.success(`Score ${data.score}/100`);
      load();
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail));
    } finally {
      setVerifying(false);
    }
  };

  if (!domain) return <AppShell><div className="text-muted-foreground">Loading…</div></AppShell>;

  return (
    <AppShell>
      <Link to="/domains" className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1 mb-4" data-testid="back-to-domains">
        <ChevronLeft className="h-3 w-3" /> Domains
      </Link>
      <PageHeader
        title={domain.name}
        description={`DKIM selector: ${domain.dkim_selector} • Mail host: ${domain.mail_host}.${domain.name}`}
        testId="domain-detail-header"
        actions={
          <Button onClick={verify} disabled={verifying} data-testid="run-verification-button">
            <RefreshCw className={`h-4 w-4 ${verifying ? "animate-spin" : ""}`} /> Run verification
          </Button>
        }
      />

      <div className="grid lg:grid-cols-[1fr_320px] gap-6">
        <div className="space-y-4">
          <SectionLabel>DNS records to publish</SectionLabel>
          {records.map((r, i) => (
            <RecordCard key={i} rec={r} />
          ))}
        </div>

        <div>
          <Card className="rounded-md border border-border p-5 sticky top-6">
            <SectionLabel>Live checks</SectionLabel>
            {!checks && (
              <div className="text-sm text-muted-foreground">Not verified yet. Click <span className="font-mono">Run verification</span>.</div>
            )}
            {checks && (
              <div>
                <CheckRow label="SPF" ok={checks.spf?.valid} detail={checks.spf?.found} />
                <CheckRow label="DKIM" ok={checks.dkim?.valid} detail={checks.dkim?.found} />
                <CheckRow label="DMARC" ok={checks.dmarc?.valid} detail={checks.dmarc?.found} />
                <CheckRow label="MX" ok={checks.mx?.valid} detail={(checks.mx?.found || []).join(", ")} />
                <div className="mt-4 pt-3 border-t border-border">
                  <div className="text-xs uppercase tracking-wider text-muted-foreground">Score</div>
                  <div className="font-mono text-2xl font-semibold mt-1" data-testid="domain-score">{domain.score ?? 0}/100</div>
                </div>
              </div>
            )}
          </Card>
        </div>
      </div>
    </AppShell>
  );
}
