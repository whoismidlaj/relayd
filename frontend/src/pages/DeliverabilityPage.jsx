import React, { useEffect, useState } from "react";
import AppShell, { PageHeader, SectionLabel } from "@/components/AppShell";
import { api, formatApiError } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { CheckCircle2, XCircle, RefreshCw, AlertCircle, ShieldAlert } from "lucide-react";
import { toast } from "sonner";

function Pill({ ok, label, error }) {
  return (
    <div className="flex items-center gap-1.5">
      {ok ? <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" /> : error ? <XCircle className="h-3.5 w-3.5 text-destructive" /> : <AlertCircle className="h-3.5 w-3.5 text-amber-500" />}
      <span className="text-xs font-mono uppercase tracking-wider">{label}</span>
    </div>
  );
}

export default function DeliverabilityPage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  const run = async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/deliverability");
      setData(data);
    } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
    finally { setLoading(false); }
  };

  useEffect(() => { run(); }, []);

  return (
    <AppShell>
      <PageHeader title="Deliverability"
        description="Live DNS scoring across all your domains: SPF, DKIM, DMARC and MX."
        testId="deliverability-header"
        actions={
          <Button onClick={run} disabled={loading} data-testid="rerun-checks-button">
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} /> Re-run checks
          </Button>
        }
      />

      <div className="grid gap-4">
        {(!data || data.domains.length === 0) && (
          <Card className="rounded-md border border-border p-10 text-center text-muted-foreground">
            No domains to check. Add a domain first.
          </Card>
        )}
        {data?.domains?.map((d) => (
          <Card key={d.id} className="rounded-md border border-border p-5" data-testid={`deliverability-card-${d.name}`}>
            <div className="flex items-center justify-between mb-4">
              <div>
                <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Domain</div>
                <div className="font-mono text-lg font-medium">{d.name}</div>
              </div>
              <div className="text-right">
                <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Score</div>
                <div className="font-mono text-2xl font-semibold">{d.score}/100</div>
                <Badge variant="outline" className={d.verified ? "text-emerald-500 border-emerald-500/40 mt-1" : "text-amber-500 border-amber-500/40 mt-1"}>
                  {d.verified ? "fully aligned" : "needs attention"}
                </Badge>
              </div>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-6 gap-3 mt-3">
              <Pill ok={d.checks.spf?.valid} label="SPF" error={!d.checks.spf?.valid} />
              <Pill ok={d.checks.dkim?.valid && d.checks.dkim?.matches_expected} label="DKIM" error={!d.checks.dkim?.valid} />
              <Pill ok={d.checks.dmarc?.valid} label="DMARC" error={!d.checks.dmarc?.valid} />
              <Pill ok={d.checks.mx?.valid} label="MX" error={!d.checks.mx?.valid} />
              <Pill ok={!d.checks.dnsbl?.listed} label="DNSBL" error={d.checks.dnsbl?.listed} />
              <Pill ok={d.checks.ptr?.valid} label="PTR" error={!d.checks.ptr?.valid} />
            </div>
            
            <div className="mt-4 pt-3 border-t border-border grid md:grid-cols-2 gap-6">
              <div className="space-y-2">
                <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground mb-3">Raw Records</div>
                <div className="text-xs"><span className="text-muted-foreground">SPF:</span> <span className="font-mono">{d.checks.spf?.found || "—"}</span></div>
                <div className="text-xs"><span className="text-muted-foreground">DMARC:</span> <span className="font-mono">{d.checks.dmarc?.found || "—"}</span></div>
                <div className="text-xs"><span className="text-muted-foreground">MX IP:</span> <span className="font-mono">{d.checks.ip || "—"}</span></div>
              </div>

              {d.checks.recommendations?.length > 0 && (
                <div className="space-y-2">
                  <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground mb-3">Diagnostics</div>
                  {d.checks.recommendations.map((r, i) => (
                    <div key={i} className={`text-xs p-2.5 rounded-md flex items-start gap-2 ${
                      r.type === 'critical' ? 'bg-red-500/10 text-red-500 border border-red-500/20' :
                      r.type === 'warning' ? 'bg-amber-500/10 text-amber-500 border border-amber-500/20' :
                      'bg-blue-500/10 text-blue-500 border border-blue-500/20'
                    }`}>
                      {r.type === 'critical' ? <ShieldAlert className="h-3.5 w-3.5 mt-0.5 shrink-0" /> : <AlertCircle className="h-3.5 w-3.5 mt-0.5 shrink-0" />}
                      <span className="leading-relaxed">{r.msg}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </Card>
        ))}
      </div>
    </AppShell>
  );
}
