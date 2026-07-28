import React, { useEffect, useState } from "react";
import AppShell, { PageHeader } from "@/components/AppShell";
import { api, formatApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
import { Plus, Trash2, KeyRound, Pencil, Info, Send } from "lucide-react";
import { toast } from "sonner";
import { DialogDescription } from "@/components/ui/dialog";

export default function MailboxesPage() {
  const [items, setItems] = useState([]);
  const [domains, setDomains] = useState([]);
  const [open, setOpen] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [pwOpen, setPwOpen] = useState(null);
  const [infoOpen, setInfoOpen] = useState(null);
  const [form, setForm] = useState({ local_part: "", domain_id: "", password: "", display_name: "", quota_mb: 1024 });
  const [newPw, setNewPw] = useState("");

  const refresh = async () => {
    try {
      const [m, d] = await Promise.all([api.get("/mailboxes"), api.get("/domains")]);
      setItems(m.data);
      setDomains(d.data);
    } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
  };

  useEffect(() => { refresh(); }, []);

  const save = async (e) => {
    e.preventDefault();
    try {
      if (editingId) {
        await api.patch(`/mailboxes/${editingId}`, { 
          display_name: form.display_name, 
          quota_mb: form.quota_mb 
        });
        toast.success("Mailbox updated");
      } else {
        await api.post("/mailboxes", form);
        toast.success("Mailbox created");
      }
      setOpen(false);
      setEditingId(null);
      setForm({ local_part: "", domain_id: "", password: "", display_name: "", quota_mb: 1024 });
      refresh();
    } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
  };

  const startEdit = (m) => {
    setEditingId(m.id);
    setForm({
      local_part: m.local_part,
      domain_id: m.domain_id,
      password: "",
      display_name: m.display_name,
      quota_mb: m.quota_mb
    });
    setOpen(true);
  };

  const startAdd = () => {
    setEditingId(null);
    setForm({ local_part: "", domain_id: "", password: "", display_name: "", quota_mb: 1024 });
    setOpen(true);
  };

  const remove = async (id) => {
    if (!confirm("Delete this mailbox?")) return;
    try {
      await api.delete(`/mailboxes/${id}`);
      toast.success("Mailbox removed");
      refresh();
    } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
  };

  const updatePassword = async (id) => {
    if (newPw.length < 6) return toast.error("Password too short");
    try {
      await api.patch(`/mailboxes/${id}`, { password: newPw });
      toast.success("Password updated");
      setPwOpen(null); setNewPw("");
    } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
  };

  return (
    <AppShell>
      <PageHeader
        title="Mailboxes"
        description="Create and manage user mailboxes. Each mailbox lives on a verified domain."
        testId="mailboxes-header"
        actions={
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
              <Button disabled={domains.length === 0} onClick={startAdd} data-testid="add-mailbox-button">
                <Plus className="h-4 w-4" /> New mailbox
              </Button>
            </DialogTrigger>
            <DialogContent data-testid="add-mailbox-dialog">
              <DialogHeader>
                <DialogTitle>{editingId ? "Edit mailbox" : "Create mailbox"}</DialogTitle>
                <DialogDescription>Configure your mailbox settings. Display names are shown to recipients, and quota limits the storage space.</DialogDescription>
              </DialogHeader>
              <form onSubmit={save} className="space-y-4">
                <div className="grid grid-cols-[1fr_120px] gap-3">
                  <div className="space-y-2">
                    <Label>Local part</Label>
                    <Input value={form.local_part} onChange={(e) => setForm({ ...form, local_part: e.target.value })}
                           disabled={!!editingId}
                           placeholder="john.doe" required data-testid="mailbox-local-input" />
                  </div>
                  <div className="space-y-2">
                    <Label>Quota (MB)</Label>
                    <Input type="number" min="64" value={form.quota_mb}
                           onChange={(e) => setForm({ ...form, quota_mb: Number(e.target.value) })}
                           data-testid="mailbox-quota-input" />
                  </div>
                </div>
                <div className="space-y-2">
                  <Label>Domain</Label>
                  <Select value={form.domain_id} onValueChange={(v) => setForm({ ...form, domain_id: v })} disabled={!!editingId}>
                    <SelectTrigger data-testid="mailbox-domain-select"><SelectValue placeholder="Select domain" /></SelectTrigger>
                    <SelectContent>
                      {domains.map((d) => <SelectItem key={d.id} value={d.id}>{d.name}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>Display name</Label>
                  <Input value={form.display_name} onChange={(e) => setForm({ ...form, display_name: e.target.value })}
                         placeholder="John Doe" data-testid="mailbox-display-input" />
                </div>
                {!editingId && (
                  <div className="space-y-2">
                    <Label>Password</Label>
                    <Input type="password" value={form.password}
                           onChange={(e) => setForm({ ...form, password: e.target.value })}
                           minLength={6} required data-testid="mailbox-password-input" />
                  </div>
                )}
                <DialogFooter><Button type="submit" data-testid="mailbox-submit">{editingId ? "Update" : "Create"}</Button></DialogFooter>
              </form>
            </DialogContent>
          </Dialog>
        }
      />

      <Card className="rounded-md border border-border overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Address</TableHead>
              <TableHead>Display</TableHead>
              <TableHead>Quota</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody data-testid="mailboxes-table-body">
            {items.length === 0 && (
              <TableRow><TableCell colSpan={5} className="text-center text-muted-foreground py-10">
                {domains.length === 0 ? "Add a domain first to create mailboxes." : "No mailboxes yet."}
              </TableCell></TableRow>
            )}
            {items.map((m) => (
              <TableRow key={m.id}>
                <TableCell className="font-mono">{m.address}</TableCell>
                <TableCell>{m.display_name}</TableCell>
                <TableCell className="font-mono text-xs">{m.quota_mb} MB</TableCell>
                <TableCell>
                  <Badge variant="outline" className={m.active ? "text-emerald-500 border-emerald-500/40" : "text-muted-foreground"}>
                    {m.active ? "active" : "disabled"}
                  </Badge>
                </TableCell>
                 <TableCell className="text-right space-x-1">
                  <Button variant="ghost" size="sm" onClick={() => startEdit(m)} data-testid={`edit-mb-${m.address}`}>
                    <Pencil className="h-3.5 w-3.5" />
                  </Button>
                  <Button variant="ghost" size="sm" onClick={() => {
                    // This is a bit hacky, but we can use window events or just trigger the sidebar button
                    document.querySelector('[data-testid="sidebar-compose-button"]')?.click();
                    // We'll need a way to pre-fill the 'from' address. 
                    // For now, it will just open the dialog.
                  }} data-testid={`send-mb-${m.address}`}>
                    <Send className="h-3.5 w-3.5" />
                  </Button>
                  <Dialog open={infoOpen === m.id} onOpenChange={(o) => setInfoOpen(o ? m.id : null)}>
                    <DialogTrigger asChild>
                      <Button variant="ghost" size="sm" data-testid={`info-mb-${m.address}`}>
                        <Info className="h-3.5 w-3.5" />
                      </Button>
                    </DialogTrigger>
                    <DialogContent>
                      <DialogHeader>
                        <DialogTitle>Mailbox Settings</DialogTitle>
                        <DialogDescription>Use these settings to connect your email client (Outlook, Gmail, etc.)</DialogDescription>
                      </DialogHeader>
                      <div className="space-y-4 py-4">
                        <div className="grid grid-cols-3 gap-2 text-sm">
                          <div className="font-semibold">Username:</div>
                          <div className="col-span-2 font-mono">{m.address}</div>
                          
                          <div className="font-semibold text-primary mt-2 col-span-3 border-b pb-1">Incoming (IMAP)</div>
                          <div className="font-semibold">Server:</div>
                          <div className="col-span-2 font-mono">{window.location.hostname}</div>
                          <div className="font-semibold">Port:</div>
                          <div className="col-span-2">993 (SSL/TLS) or 143 (STARTTLS)</div>
                          
                          <div className="font-semibold text-primary mt-2 col-span-3 border-b pb-1">Outgoing (SMTP)</div>
                          <div className="font-semibold">Server:</div>
                          <div className="col-span-2 font-mono">{window.location.hostname}</div>
                          <div className="font-semibold">Port:</div>
                          <div className="col-span-2">465 (SSL/TLS) or 587 (STARTTLS)</div>
                        </div>
                      </div>
                    </DialogContent>
                  </Dialog>
                  <Dialog open={pwOpen === m.id} onOpenChange={(o) => { setPwOpen(o ? m.id : null); setNewPw(""); }}>
                    <DialogTrigger asChild>
                      <Button variant="ghost" size="sm" data-testid={`change-pw-${m.address}`}>
                        <KeyRound className="h-3.5 w-3.5" />
                      </Button>
                    </DialogTrigger>
                    <DialogContent>
                      <DialogHeader>
                        <DialogTitle>Change password</DialogTitle>
                        <DialogDescription>Update the password for {m.address}. This will affect IMAP and SMTP login.</DialogDescription>
                      </DialogHeader>
                      <div className="space-y-2">
                        <Label>New password</Label>
                        <Input type="password" value={newPw} onChange={(e) => setNewPw(e.target.value)}
                               minLength={6} data-testid="new-password-input" />
                      </div>
                      <DialogFooter><Button onClick={() => updatePassword(m.id)} data-testid="save-password-button">Update</Button></DialogFooter>
                    </DialogContent>
                  </Dialog>
                  <Button variant="ghost" size="sm" onClick={() => remove(m.id)} data-testid={`delete-mb-${m.address}`}>
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
