import React, { useEffect, useState } from "react";
import AppShell, { PageHeader } from "@/components/AppShell";
import { api, formatApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter,
} from "@/components/ui/dialog";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { Plus, Trash2, Send, Star, AlertCircle } from "lucide-react";
import { toast } from "sonner";

const PROVIDER_META = {
  smtp:    { label: "Generic SMTP", wired: true,  fields: ["host", "port", "username", "password", "use_tls", "use_ssl"] },
  resend:  { label: "Resend",       wired: true,  fields: ["api_key"] },
  ses:     { label: "Amazon SES",   wired: false, fields: ["access_key_id", "secret_access_key", "region"] },
  brevo:   { label: "Brevo",        wired: false, fields: ["api_key"] },
  smtp2go: { label: "SMTP2GO",      wired: false, fields: ["api_key"] },
  direct:  { label: "System (Direct MX)", wired: true, fields: [] },
};

const DEFAULT_CFG = {
  smtp: { host: "", port: 587, username: "", password: "", use_tls: true, use_ssl: false },
  resend: { api_key: "" },
  ses: { access_key_id: "", secret_access_key: "", region: "us-east-1" },
  brevo: { api_key: "" },
  smtp2go: { api_key: "" },
  direct: {},
};

function ProviderFields({ type, cfg, setCfg }) {
  if (type === "smtp") {
    return (
      <>
        <div className="grid grid-cols-[1fr_100px] gap-3">
          <div className="space-y-2"><Label>Host</Label>
            <Input value={cfg.host} onChange={(e) => setCfg({ ...cfg, host: e.target.value })}
                   placeholder="smtp.example.com" required data-testid="smtp-host-input" />
          </div>
          <div className="space-y-2"><Label>Port</Label>
            <Input type="number" value={cfg.port} onChange={(e) => setCfg({ ...cfg, port: Number(e.target.value) })}
                   data-testid="smtp-port-input" />
          </div>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-2"><Label>Username</Label>
            <Input value={cfg.username} onChange={(e) => setCfg({ ...cfg, username: e.target.value })}
                   data-testid="smtp-username-input" /></div>
          <div className="space-y-2"><Label>Password</Label>
            <Input type="password" value={cfg.password} onChange={(e) => setCfg({ ...cfg, password: e.target.value })}
                   data-testid="smtp-password-input" /></div>
        </div>
        <div className="flex items-center gap-6 text-sm">
          <label className="flex items-center gap-2"><input type="checkbox" checked={cfg.use_tls}
            onChange={(e) => setCfg({ ...cfg, use_tls: e.target.checked })} /> STARTTLS</label>
          <label className="flex items-center gap-2"><input type="checkbox" checked={cfg.use_ssl}
            onChange={(e) => setCfg({ ...cfg, use_ssl: e.target.checked })} /> SSL/TLS (port 465)</label>
        </div>
      </>
    );
  }
  if (type === "resend") {
    return (
      <div className="space-y-2">
        <Label>API Key</Label>
        <Input value={cfg.api_key} onChange={(e) => setCfg({ ...cfg, api_key: e.target.value })}
               placeholder="re_..." required data-testid="resend-apikey-input" />
        <p className="text-xs text-muted-foreground">Get yours at resend.com/api-keys</p>
      </div>
    );
  }
  if (type === "ses") {
    return (
      <>
        <div className="space-y-2"><Label>Access Key ID</Label>
          <Input value={cfg.access_key_id} onChange={(e) => setCfg({ ...cfg, access_key_id: e.target.value })} /></div>
        <div className="space-y-2"><Label>Secret Access Key</Label>
          <Input type="password" value={cfg.secret_access_key}
                 onChange={(e) => setCfg({ ...cfg, secret_access_key: e.target.value })} /></div>
        <div className="space-y-2"><Label>Region</Label>
          <Input value={cfg.region} onChange={(e) => setCfg({ ...cfg, region: e.target.value })} /></div>
      </>
    );
  }
  if (type === "direct") {
    return (
      <div className="p-4 rounded-md border border-border bg-muted/30 text-sm space-y-2">
        <div className="flex items-center gap-2 font-semibold text-foreground">
          <AlertCircle className="h-4 w-4 text-blue-500" />
          Zero-Config Required
        </div>
        <p className="text-muted-foreground leading-relaxed">
          The system will perform <strong>MX Lookups</strong> and deliver mail directly to the recipient's servers. 
          Make sure your server IP has a <strong>PTR record</strong> and <strong>Port 25</strong> is open.
        </p>
      </div>
    );
  }
  // brevo / smtp2go
  return (
    <div className="space-y-2">
      <Label>API Key</Label>
      <Input value={cfg.api_key} onChange={(e) => setCfg({ ...cfg, api_key: e.target.value })} required />
    </div>
  );
}

export default function RelaysPage() {
  const [items, setItems] = useState([]);
  const [open, setOpen] = useState(false);
  const [testOpen, setTestOpen] = useState(false);
  const [form, setForm] = useState({ name: "", type: "resend", priority: 100, is_default: false });
  const [cfg, setCfg] = useState({ ...DEFAULT_CFG.resend });
  const [test, setTest] = useState({ from_email: "onboarding@resend.dev", to: "", subject: "Hello from Relayd", body: "This is a test from Relayd. ✉️", relay_id: "" });
  const [sending, setSending] = useState(false);

  const refresh = async () => {
    try {
      const { data } = await api.get("/relays");
      setItems(data);
    } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
  };

  useEffect(() => { refresh(); }, []);

  const create = async (e) => {
    e.preventDefault();
    try {
      await api.post("/relays", { ...form, config: cfg });
      toast.success("Relay added");
      setOpen(false);
      setForm({ name: "", type: "resend", priority: 100, is_default: false });
      setCfg({ ...DEFAULT_CFG.resend });
      refresh();
    } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
  };

  const remove = async (id) => {
    if (!confirm("Delete this relay?")) return;
    try { await api.delete(`/relays/${id}`); refresh(); }
    catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
  };

  const setDefault = async (id) => {
    try {
      await api.patch(`/relays/${id}`, { is_default: true });
      toast.success("Default relay updated");
      refresh();
    } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
  };

  const sendTest = async (e) => {
    e.preventDefault();
    setSending(true);
    try {
      const payload = { ...test };
      if (!payload.relay_id) delete payload.relay_id;
      const { data } = await api.post("/send/test", payload);
      if (data.status === "sent") toast.success(`Sent via ${data.provider_name}`);
      else toast.error(`Failed: ${data.error || "unknown"}`);
    } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
    finally { setSending(false); }
  };

  const changeType = (t) => {
    setForm({ ...form, type: t });
    setCfg({ ...DEFAULT_CFG[t] });
  };

  return (
    <AppShell>
      <PageHeader
        title="Relay providers"
        description="Outbound providers used to send mail. Set a default and order by priority for automatic failover."
        testId="relays-header"
        actions={
          <div className="flex gap-2">
            <Dialog open={testOpen} onOpenChange={setTestOpen}>
              <DialogTrigger asChild>
                <Button variant="outline" disabled={items.length === 0} data-testid="open-test-email-button">
                  <Send className="h-4 w-4" /> Send test email
                </Button>
              </DialogTrigger>
              <DialogContent data-testid="test-email-dialog">
                <DialogHeader><DialogTitle>Send a test email</DialogTitle></DialogHeader>
                <form onSubmit={sendTest} className="space-y-4">
                  <div className="space-y-2"><Label>From</Label>
                    <Input value={test.from_email} onChange={(e) => setTest({ ...test, from_email: e.target.value })}
                           required data-testid="test-from-input" />
                  </div>
                  <div className="space-y-2"><Label>To</Label>
                    <Input type="email" value={test.to} onChange={(e) => setTest({ ...test, to: e.target.value })}
                           required data-testid="test-to-input" />
                  </div>
                  <div className="space-y-2"><Label>Subject</Label>
                    <Input value={test.subject} onChange={(e) => setTest({ ...test, subject: e.target.value })}
                           required data-testid="test-subject-input" />
                  </div>
                  <div className="space-y-2"><Label>Body</Label>
                    <Textarea rows={4} value={test.body} onChange={(e) => setTest({ ...test, body: e.target.value })}
                              data-testid="test-body-input" />
                  </div>
                  <div className="space-y-2"><Label>Relay (optional — default + failover otherwise)</Label>
                    <Select value={test.relay_id || "__default__"}
                      onValueChange={(v) => setTest({ ...test, relay_id: v === "__default__" ? "" : v })}>
                      <SelectTrigger data-testid="test-relay-select"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="__default__">Use default + failover</SelectItem>
                        {items.map((r) => <SelectItem key={r.id} value={r.id}>{r.name} ({r.type})</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </div>
                  <DialogFooter>
                    <Button type="submit" disabled={sending} data-testid="send-test-submit">
                      {sending ? "Sending…" : "Send"}
                    </Button>
                  </DialogFooter>
                </form>
              </DialogContent>
            </Dialog>

            <Dialog open={open} onOpenChange={setOpen}>
              <DialogTrigger asChild>
                <Button data-testid="add-relay-button"><Plus className="h-4 w-4" /> Add provider</Button>
              </DialogTrigger>
              <DialogContent data-testid="add-relay-dialog" className="max-h-[90vh] overflow-y-auto">
                <DialogHeader><DialogTitle>Add relay provider</DialogTitle></DialogHeader>
                <form onSubmit={create} className="space-y-4">
                  <div className="grid grid-cols-2 gap-3">
                    <div className="space-y-2"><Label>Name</Label>
                      <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
                             placeholder="Production Resend" required data-testid="relay-name-input" /></div>
                    <div className="space-y-2"><Label>Type</Label>
                      <Select value={form.type} onValueChange={changeType}>
                        <SelectTrigger data-testid="relay-type-select"><SelectValue /></SelectTrigger>
                        <SelectContent>
                          {Object.entries(PROVIDER_META).map(([k, m]) => (
                            <SelectItem key={k} value={k}>{m.label}{!m.wired && " (config only)"}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  </div>

                  {!PROVIDER_META[form.type].wired && (
                    <div className="text-xs flex items-start gap-2 border border-amber-500/30 bg-amber-500/5 text-amber-600 dark:text-amber-400 rounded-sm p-3">
                      <AlertCircle className="h-3.5 w-3.5 mt-0.5 shrink-0" />
                      <span>This provider is config-only in the current MVP. Sending will return an error until wired. Use Generic SMTP or Resend to actually send.</span>
                    </div>
                  )}

                  <ProviderFields type={form.type} cfg={cfg} setCfg={setCfg} />

                  <div className="grid grid-cols-[1fr_140px] gap-3">
                    <div className="space-y-2"><Label>Priority (lower = first)</Label>
                      <Input type="number" value={form.priority}
                             onChange={(e) => setForm({ ...form, priority: Number(e.target.value) })}
                             data-testid="relay-priority-input" /></div>
                    <div className="space-y-2"><Label>&nbsp;</Label>
                      <label className="flex items-center gap-2 h-9 text-sm">
                        <input type="checkbox" checked={form.is_default}
                               onChange={(e) => setForm({ ...form, is_default: e.target.checked })}
                               data-testid="relay-default-checkbox" />
                        Set as default
                      </label>
                    </div>
                  </div>
                  <DialogFooter><Button type="submit" data-testid="relay-submit">Add provider</Button></DialogFooter>
                </form>
              </DialogContent>
            </Dialog>
          </div>
        }
      />

      <Card className="rounded-md border border-border overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Type</TableHead>
              <TableHead>Priority</TableHead>
              <TableHead>Default</TableHead>
              <TableHead>Config</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody data-testid="relays-table-body">
            {items.length === 0 && (
              <TableRow><TableCell colSpan={6} className="text-center text-muted-foreground py-10">
                No relays yet. Add Resend, SMTP, or use <strong>System (Direct MX)</strong> to start sending.
              </TableCell></TableRow>
            )}
            {items.map((r) => (
              <TableRow key={r.id}>
                <TableCell className="font-medium">{r.name}</TableCell>
                <TableCell>
                  <Badge variant="outline">{PROVIDER_META[r.type]?.label || r.type}</Badge>
                </TableCell>
                <TableCell className="font-mono">{r.priority}</TableCell>
                <TableCell>
                  {r.is_default
                    ? <Badge variant="outline" className="text-amber-500 border-amber-500/40"><Star className="h-3 w-3 mr-1" /> default</Badge>
                    : <Button size="sm" variant="ghost" onClick={() => setDefault(r.id)} data-testid={`make-default-${r.name}`}>Make default</Button>}
                </TableCell>
                <TableCell className="font-mono text-xs text-muted-foreground max-w-xs truncate">
                  {Object.entries(r.config || {}).map(([k, v]) => `${k}=${v}`).join(" • ")}
                </TableCell>
                <TableCell className="text-right">
                  <Button variant="ghost" size="sm" onClick={() => remove(r.id)} data-testid={`delete-relay-${r.name}`}>
                    <Trash2 className="h-3.5 w-3.5 text-destructive" />
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>
    </AppShell>
  );
}
