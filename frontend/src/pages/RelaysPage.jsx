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
import { Plus, Trash2, Send, Star, AlertCircle, Pencil, X, ExternalLink, Hexagon, Cloud, Zap, Mail, Server, Box, ChevronLeft } from "lucide-react";
import { toast } from "sonner";
import { DialogDescription } from "@/components/ui/dialog";
import TagsInput from "@/components/TagsInput";

const PROVIDER_META = {
  resend:  { label: "Resend",       icon: Hexagon, wired: true, desc: "Modern email API for developers. Great deliverability.", link: "https://resend.com/api-keys" },
  ses:     { label: "Amazon SES",   icon: Cloud,   wired: true, desc: "Highly scalable and cost-effective email service.", link: "https://aws.amazon.com/ses/" },
  brevo:   { label: "Brevo",        icon: Zap,     wired: true, desc: "Reliable transactional email service.", link: "https://www.brevo.com/" },
  smtp2go: { label: "SMTP2GO",      icon: Mail,    wired: true, desc: "Robust SMTP provider with good inbox placement.", link: "https://www.smtp2go.com/" },
  smtp:    { label: "Generic SMTP", icon: Server,  wired: true, desc: "Standard SMTP protocol for external mail servers.", link: null },
  direct:  { label: "System MX",    icon: Box,     wired: true, desc: "Deliver directly using your VPS network.", link: null },
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
  const meta = PROVIDER_META[type];

  return (
    <div className="space-y-4 border border-border p-4 rounded-md bg-muted/10 relative mt-4">
      <div className="flex items-start justify-between mb-4 border-b border-border pb-3">
        <div className="flex items-center gap-3">
          {meta?.icon && <div className="h-8 w-8 rounded-full bg-primary/10 text-primary flex items-center justify-center shrink-0">
            <meta.icon className="h-4 w-4" />
          </div>}
          <div>
            <h4 className="font-semibold text-sm">{meta?.label} Connection Details</h4>
            <p className="text-xs text-muted-foreground mt-0.5">{meta?.desc}</p>
          </div>
        </div>
        {meta?.link && (
          <a href={meta.link} target="_blank" rel="noreferrer" className="text-xs flex items-center gap-1 text-primary hover:underline shrink-0">
            Docs <ExternalLink className="h-3 w-3" />
          </a>
        )}
      </div>

      {type === "smtp" && (
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
          <div className="flex items-center gap-6 text-sm pt-2">
            <label className="flex items-center gap-2 cursor-pointer"><input type="checkbox" checked={cfg.use_tls}
              onChange={(e) => setCfg({ ...cfg, use_tls: e.target.checked })} className="rounded bg-background" /> STARTTLS</label>
            <label className="flex items-center gap-2 cursor-pointer"><input type="checkbox" checked={cfg.use_ssl}
              onChange={(e) => setCfg({ ...cfg, use_ssl: e.target.checked })} className="rounded bg-background" /> SSL/TLS (port 465)</label>
          </div>
        </>
      )}

      {type === "resend" && (
        <div className="space-y-2">
          <Label>API Key</Label>
          <Input value={cfg.api_key} onChange={(e) => setCfg({ ...cfg, api_key: e.target.value })}
                 placeholder="re_..." required data-testid="resend-apikey-input" type="password" />
        </div>
      )}

      {type === "ses" && (
        <>
          <div className="space-y-2"><Label>Access Key ID</Label>
            <Input value={cfg.access_key_id} onChange={(e) => setCfg({ ...cfg, access_key_id: e.target.value })} /></div>
          <div className="space-y-2"><Label>Secret Access Key</Label>
            <Input type="password" value={cfg.secret_access_key}
                   onChange={(e) => setCfg({ ...cfg, secret_access_key: e.target.value })} /></div>
          <div className="space-y-2"><Label>Region</Label>
            <Input value={cfg.region} onChange={(e) => setCfg({ ...cfg, region: e.target.value })} placeholder="us-east-1" /></div>
        </>
      )}

      {type === "direct" && (
        <div className="p-3 rounded-md border border-blue-500/20 bg-blue-500/5 text-sm space-y-2">
          <div className="flex items-center gap-2 font-semibold text-blue-600 dark:text-blue-400">
            <AlertCircle className="h-4 w-4" /> Zero-Config Required
          </div>
          <p className="text-muted-foreground text-xs leading-relaxed">
            The system will perform <strong>MX Lookups</strong> and deliver mail directly to the recipient's servers. 
            Make sure your server IP has a <strong>PTR record</strong> and <strong>Port 25</strong> is open outbound.
          </p>
        </div>
      )}

      {(type === "brevo" || type === "smtp2go") && (
        <div className="space-y-2">
          <Label>API Key</Label>
          <Input value={cfg.api_key} onChange={(e) => setCfg({ ...cfg, api_key: e.target.value })} required type="password" />
        </div>
      )}
    </div>
  );
}

export default function RelaysPage() {
  const [items, setItems] = useState([]);
  const [open, setOpen] = useState(false);
  const [step, setStep] = useState(1);
  const [testOpen, setTestOpen] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState({ name: "", type: "resend", priority: 100, is_default: false, daily_quota: 0, weight: 100, match_domains: "", match_tags: "" });
  const [cfg, setCfg] = useState({ ...DEFAULT_CFG.resend });
  const [test, setTest] = useState({ from_email: "onboarding@resend.dev", to: "", subject: "Hello from Relayd", body: "This is a test from Relayd. ✉️", relay_id: "", tags: "" });
  const [sending, setSending] = useState(false);

  const refresh = async () => {
    try {
      const { data } = await api.get("/relays");
      setItems(data);
    } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
  };

  useEffect(() => { refresh(); }, []);

  const save = async (e) => {
    e.preventDefault();
    try {
      const payload = { 
        ...form, 
        match_domains: form.match_domains ? form.match_domains.split(",").map(s => s.trim()).filter(Boolean) : [],
        match_tags: form.match_tags ? form.match_tags.split(",").map(s => s.trim()).filter(Boolean) : [],
        config: cfg 
      };

      if (editingId) {
        await api.patch(`/relays/${editingId}`, payload);
        toast.success("Relay updated");
      } else {
        await api.post("/relays", payload);
        toast.success("Relay added");
      }
      
      setOpen(false);
      setEditingId(null);
      setForm({ name: "", type: "resend", priority: 100, is_default: false, daily_quota: 0, weight: 100, match_domains: "", match_tags: "" });
      setCfg({ ...DEFAULT_CFG.resend });
      refresh();
    } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
  };

  const startEdit = (r) => {
    setEditingId(r.id);
    setForm({
      name: r.name,
      type: r.type,
      priority: r.priority,
      is_default: r.is_default,
      daily_quota: r.daily_quota,
      weight: r.weight,
      match_domains: (r.match_domains || []).join(", "),
      match_tags: (r.match_tags || []).join(", "),
    });
    setCfg({ ...r.config });
    setStep(2); // Skip grid
    setOpen(true);
  };

  const startAdd = () => {
    setEditingId(null);
    setForm({ name: "", type: "resend", priority: 100, is_default: false, daily_quota: 0, weight: 100, match_domains: "", match_tags: "" });
    setCfg({ ...DEFAULT_CFG.resend });
    setStep(1); // Show grid
    setOpen(true);
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
      const payload = { ...test, tags: test.tags ? test.tags.split(",").map(s => s.trim()).filter(Boolean) : [] };
      if (!payload.relay_id) delete payload.relay_id;
      const { data } = await api.post("/send/test", payload);
      if (data.status === "sent") toast.success(`Sent via ${data.provider_name}`);
      else toast.error(`Failed: ${data.error || "unknown"}`);
    } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
    finally { setSending(false); }
  };

  const changeType = (t) => {
    setForm({ ...form, type: t, name: PROVIDER_META[t].label });
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
                  <Send className="h-4 w-4 mr-2" /> Send test
                </Button>
              </DialogTrigger>
              <DialogContent data-testid="test-email-dialog">
                <DialogHeader>
                  <DialogTitle>Send a test email</DialogTitle>
                  <DialogDescription>Quickly verify that your relay configuration is working correctly.</DialogDescription>
                </DialogHeader>
                <form onSubmit={sendTest} className="space-y-4 mt-2">
                  <div className="grid grid-cols-2 gap-3">
                    <div className="space-y-2"><Label>From</Label>
                      <Input value={test.from_email} onChange={(e) => setTest({ ...test, from_email: e.target.value })} required />
                    </div>
                    <div className="space-y-2"><Label>To</Label>
                      <Input type="email" value={test.to} onChange={(e) => setTest({ ...test, to: e.target.value })} required />
                    </div>
                  </div>
                  <div className="space-y-2"><Label>Subject</Label>
                    <Input value={test.subject} onChange={(e) => setTest({ ...test, subject: e.target.value })} required />
                  </div>
                  <div className="space-y-2"><Label>Body</Label>
                    <Textarea rows={3} value={test.body} onChange={(e) => setTest({ ...test, body: e.target.value })} />
                  </div>
                  <div className="space-y-2"><Label>Tags</Label>
                    <TagsInput 
                      value={test.tags} 
                      onChange={(v) => setTest({ ...test, tags: v })} 
                      placeholder="Add tag..."
                      suggestions={["test", "system"]}
                    />
                  </div>
                  <div className="space-y-2"><Label>Force Specific Relay</Label>
                    <Select value={test.relay_id || "__default__"} onValueChange={(v) => setTest({ ...test, relay_id: v === "__default__" ? "" : v })}>
                      <SelectTrigger><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="__default__">Use routing rules (Default)</SelectItem>
                        {items.map((r) => <SelectItem key={r.id} value={r.id}>{r.name}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </div>
                  <DialogFooter>
                    <Button type="submit" disabled={sending}>{sending ? "Sending…" : "Send Email"}</Button>
                  </DialogFooter>
                </form>
              </DialogContent>
            </Dialog>

            <Dialog open={open} onOpenChange={(val) => {
              setOpen(val);
              if (!val) {
                // reset state when closing
                setTimeout(() => { setStep(1); setEditingId(null); }, 300);
              }
            }}>
              <DialogTrigger asChild>
                <Button onClick={startAdd} data-testid="add-relay-button"><Plus className="h-4 w-4 mr-1" /> Add provider</Button>
              </DialogTrigger>
              <DialogContent data-testid="add-relay-dialog" className="max-w-3xl max-h-[90vh] overflow-y-auto">
                {step === 1 ? (
                  <>
                    <DialogHeader>
                      <DialogTitle>Select Provider Platform</DialogTitle>
                      <DialogDescription>Choose the mail platform or protocol you want to connect.</DialogDescription>
                    </DialogHeader>
                    <div className="grid grid-cols-2 md:grid-cols-3 gap-4 py-4">
                      {Object.entries(PROVIDER_META).map(([k, m]) => {
                        const Icon = m.icon;
                        return (
                          <button 
                            key={k} 
                            type="button"
                            onClick={() => { changeType(k); setStep(2); }}
                            className="flex flex-col items-center justify-center p-6 text-center border border-border rounded-xl hover:border-primary hover:bg-primary/5 transition-all outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                          >
                            <Icon className="h-8 w-8 mb-3 text-muted-foreground" />
                            <h3 className="font-semibold text-sm mb-1 text-foreground">{m.label}</h3>
                            <p className="text-[10px] text-muted-foreground leading-tight">{m.desc}</p>
                          </button>
                        );
                      })}
                    </div>
                  </>
                ) : (
                  <>
                    <DialogHeader className="mb-2">
                      <div className="flex items-center gap-2">
                        {!editingId && (
                          <Button type="button" variant="ghost" size="sm" onClick={() => setStep(1)} className="-ml-2 h-8 px-2 text-muted-foreground hover:text-foreground">
                             <ChevronLeft className="h-4 w-4 mr-1" /> Back
                          </Button>
                        )}
                        <DialogTitle>{editingId ? "Edit" : "Configure"} {PROVIDER_META[form.type]?.label} Provider</DialogTitle>
                      </div>
                      <DialogDescription>Set up credentials, limits, and smart routing rules.</DialogDescription>
                    </DialogHeader>
                    
                    <form onSubmit={save} className="space-y-6">
                      <div className="space-y-2">
                        <Label>Display Name</Label>
                        <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
                               placeholder="E.g. Production Resend" required />
                      </div>

                      <ProviderFields type={form.type} cfg={cfg} setCfg={setCfg} />

                      <div className="bg-muted/30 border border-border rounded-md p-4 space-y-4">
                        <h4 className="font-semibold text-sm mb-2">Routing & Limits</h4>
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                          <div className="space-y-2"><Label>Priority</Label>
                            <Input type="number" value={form.priority} onChange={(e) => setForm({ ...form, priority: parseInt(e.target.value) })} />
                            <p className="text-[10px] text-muted-foreground">Lower runs first (e.g. 10 runs before 20).</p>
                          </div>
                          <div className="space-y-2"><Label>Load Weight</Label>
                            <Input type="number" value={form.weight} onChange={(e) => setForm({ ...form, weight: parseInt(e.target.value) })} />
                            <p className="text-[10px] text-muted-foreground">Traffic split for equal priorities.</p>
                          </div>
                          <div className="space-y-2"><Label>Daily Quota</Label>
                            <Input type="number" value={form.daily_quota} onChange={(e) => setForm({ ...form, daily_quota: parseInt(e.target.value) })} />
                            <p className="text-[10px] text-muted-foreground">0 = unlimited</p>
                          </div>
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-2">
                          <div className="space-y-2"><Label>Match Domains</Label>
                            <TagsInput 
                              value={form.match_domains} 
                              onChange={(v) => setForm({ ...form, match_domains: v })} 
                              placeholder="gmail.com"
                              suggestions={["gmail.com", "yahoo.com", "outlook.com"]}
                            />
                            <p className="text-[10px] text-muted-foreground">Force this relay for specific recipient domains.</p>
                          </div>
                          <div className="space-y-2"><Label>Match Tags</Label>
                            <TagsInput 
                              value={form.match_tags} 
                              onChange={(v) => setForm({ ...form, match_tags: v })} 
                              placeholder="marketing"
                              suggestions={["transactional", "marketing", "welcome", "system", "mailbox"]}
                            />
                            <p className="text-[10px] text-muted-foreground">Force this relay when these tags are passed via API.</p>
                          </div>
                        </div>
                      </div>

                      <div className="flex items-center justify-between">
                        <label className="flex items-center gap-2 cursor-pointer text-sm font-medium">
                          <input type="checkbox" checked={form.is_default}
                                  onChange={(e) => setForm({ ...form, is_default: e.target.checked })}
                                  className="rounded bg-background" />
                          Set as default fallback relay
                        </label>
                        <DialogFooter><Button type="submit">{editingId ? "Save Changes" : "Create Relay"}</Button></DialogFooter>
                      </div>
                    </form>
                  </>
                )}
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
              <TableHead className="hidden md:table-cell">Usage</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Default</TableHead>
              <TableHead className="hidden xl:table-cell">Rules</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody data-testid="relays-table-body">
            {items.length === 0 && (
              <TableRow><TableCell colSpan={8} className="text-center text-muted-foreground py-10">
                No relays yet. Add Resend, SMTP, or use <strong>System (Direct MX)</strong> to start sending.
              </TableCell></TableRow>
            )}
            {items.map((r) => (
              <TableRow key={r.id}>
                <TableCell className="font-medium">{r.name}</TableCell>
                <TableCell>
                  <div className="flex items-center gap-2">
                    {PROVIDER_META[r.type]?.icon && React.createElement(PROVIDER_META[r.type].icon, { className: "h-3.5 w-3.5 text-muted-foreground" })}
                    <Badge variant="outline">{PROVIDER_META[r.type]?.label || r.type}</Badge>
                  </div>
                </TableCell>
                <TableCell className="font-mono">{r.priority} <span className="text-muted-foreground text-[10px] ml-1">(w:{r.weight || 100})</span></TableCell>
                <TableCell className="hidden md:table-cell">
                  <div className="flex flex-col gap-1.5">
                    {r.daily_quota && r.daily_quota > 0 ? (
                      <div className="flex flex-col gap-1 w-32">
                        <div className="text-xs font-medium flex justify-between">
                          <span>{r.usage_today || 0} today</span>
                          <span className="text-muted-foreground">/ {r.daily_quota}</span>
                        </div>
                        <div className="w-full bg-muted rounded-full h-1.5 overflow-hidden">
                          <div 
                            className={`h-1.5 rounded-full ${(r.usage_today || 0) >= r.daily_quota ? "bg-red-500" : "bg-primary"}`} 
                            style={{ width: `${Math.min(100, ((r.usage_today || 0) / r.daily_quota) * 100)}%` }} 
                          />
                        </div>
                      </div>
                    ) : (
                      <div className="flex flex-col gap-0.5">
                        <span className="text-xs font-medium text-foreground">{r.usage_today || 0} today</span>
                        <span className="text-[10px] text-muted-foreground">Unlimited quota</span>
                      </div>
                    )}
                    <span className="text-[10px] text-muted-foreground font-mono">
                      Lifetime: {r.total_sends || 0} sent ({r.successful_sends || 0} ok)
                    </span>
                  </div>
                </TableCell>
                <TableCell>
                  {!r.health_status || r.health_status === "healthy" ? (
                    <Badge variant="outline" className="bg-emerald-500/10 text-emerald-500 border-emerald-500/20 shadow-none">Healthy</Badge>
                  ) : r.health_status === "rate_limited" ? (
                    <Badge variant="outline" className="bg-amber-500/10 text-amber-500 border-amber-500/20 shadow-none">Rate limited</Badge>
                  ) : r.health_status === "high_bounce_rate" ? (
                    <Badge variant="outline" className="bg-orange-500/10 text-orange-500 border-orange-500/20 shadow-none">High bounce</Badge>
                  ) : (
                    <Badge variant="outline" className="bg-red-500/10 text-red-500 border-red-500/20 shadow-none">Error</Badge>
                  )}
                </TableCell>
                <TableCell>
                  {r.is_default
                    ? <Badge variant="outline" className="text-amber-500 border-amber-500/40"><Star className="h-3 w-3 mr-1 fill-amber-500" /> default</Badge>
                    : <Button size="sm" variant="ghost" onClick={() => setDefault(r.id)}>Make default</Button>}
                </TableCell>
                <TableCell className="font-mono text-[10px] text-muted-foreground max-w-xs overflow-hidden hidden xl:table-cell">
                  <div className="space-y-1">
                    {r.match_domains?.length > 0 && <div><span className="font-semibold text-primary">Domains:</span> {r.match_domains.join(", ")}</div>}
                    {r.match_tags?.length > 0 && <div><span className="font-semibold text-primary">Tags:</span> {r.match_tags.join(", ")}</div>}
                    {(!r.match_domains?.length && !r.match_tags?.length) && <span className="opacity-50">Global</span>}
                  </div>
                </TableCell>
                 <TableCell className="text-right space-x-1">
                  <Button variant="ghost" size="sm" onClick={() => startEdit(r)} data-testid={`edit-relay-${r.name}`}>
                    <Pencil className="h-3.5 w-3.5" />
                  </Button>
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
