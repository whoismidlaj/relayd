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
import { Plus, Trash2, KeyRound } from "lucide-react";
import { toast } from "sonner";

export default function MailboxesPage() {
  const [items, setItems] = useState([]);
  const [domains, setDomains] = useState([]);
  const [open, setOpen] = useState(false);
  const [pwOpen, setPwOpen] = useState(null);
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

  const create = async (e) => {
    e.preventDefault();
    try {
      await api.post("/mailboxes", form);
      toast.success("Mailbox created");
      setOpen(false);
      setForm({ local_part: "", domain_id: "", password: "", display_name: "", quota_mb: 1024 });
      refresh();
    } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
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
              <Button disabled={domains.length === 0} data-testid="add-mailbox-button">
                <Plus className="h-4 w-4" /> New mailbox
              </Button>
            </DialogTrigger>
            <DialogContent data-testid="add-mailbox-dialog">
              <DialogHeader><DialogTitle>Create mailbox</DialogTitle></DialogHeader>
              <form onSubmit={create} className="space-y-4">
                <div className="grid grid-cols-[1fr_120px] gap-3">
                  <div className="space-y-2">
                    <Label>Local part</Label>
                    <Input value={form.local_part} onChange={(e) => setForm({ ...form, local_part: e.target.value })}
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
                  <Select value={form.domain_id} onValueChange={(v) => setForm({ ...form, domain_id: v })}>
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
                <div className="space-y-2">
                  <Label>Password</Label>
                  <Input type="password" value={form.password}
                         onChange={(e) => setForm({ ...form, password: e.target.value })}
                         minLength={6} required data-testid="mailbox-password-input" />
                </div>
                <DialogFooter><Button type="submit" data-testid="mailbox-submit">Create</Button></DialogFooter>
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
                  <Dialog open={pwOpen === m.id} onOpenChange={(o) => { setPwOpen(o ? m.id : null); setNewPw(""); }}>
                    <DialogTrigger asChild>
                      <Button variant="ghost" size="sm" data-testid={`change-pw-${m.address}`}>
                        <KeyRound className="h-3.5 w-3.5" /> Password
                      </Button>
                    </DialogTrigger>
                    <DialogContent>
                      <DialogHeader><DialogTitle>Change password for {m.address}</DialogTitle></DialogHeader>
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
