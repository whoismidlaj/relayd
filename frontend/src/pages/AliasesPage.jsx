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
import { Switch } from "@/components/ui/switch";
import { Plus, Trash2, ArrowRight } from "lucide-react";
import { toast } from "sonner";

export default function AliasesPage() {
  const [items, setItems] = useState([]);
  const [domains, setDomains] = useState([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ local_part: "", domain_id: "", destinations: "", enabled: true });

  const refresh = async () => {
    try {
      const [a, d] = await Promise.all([api.get("/aliases"), api.get("/domains")]);
      setItems(a.data); setDomains(d.data);
    } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
  };

  useEffect(() => { refresh(); }, []);

  const create = async (e) => {
    e.preventDefault();
    try {
      const destinations = form.destinations.split(/[,\s]+/).filter(Boolean);
      await api.post("/aliases", {
        local_part: form.local_part,
        domain_id: form.domain_id,
        destinations,
        enabled: form.enabled,
      });
      toast.success("Alias created");
      setOpen(false);
      setForm({ local_part: "", domain_id: "", destinations: "", enabled: true });
      refresh();
    } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
  };

  const toggle = async (id, enabled) => {
    try {
      await api.patch(`/aliases/${id}`, { enabled });
      refresh();
    } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
  };

  const remove = async (id) => {
    if (!confirm("Delete this alias?")) return;
    try {
      await api.delete(`/aliases/${id}`);
      refresh();
    } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
  };

  return (
    <AppShell>
      <PageHeader
        title="Aliases"
        description="Forward incoming mail to external destinations. Use * as the local part for a catch-all alias."
        testId="aliases-header"
        actions={
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
              <Button disabled={domains.length === 0} data-testid="add-alias-button">
                <Plus className="h-4 w-4" /> New alias
              </Button>
            </DialogTrigger>
            <DialogContent data-testid="add-alias-dialog">
              <DialogHeader><DialogTitle>Create alias</DialogTitle></DialogHeader>
              <form onSubmit={create} className="space-y-4">
                <div className="space-y-2">
                  <Label>Local part (use <code className="font-mono">*</code> for catch-all)</Label>
                  <Input value={form.local_part} onChange={(e) => setForm({ ...form, local_part: e.target.value })}
                         placeholder="hello or *" required data-testid="alias-local-input" />
                </div>
                <div className="space-y-2">
                  <Label>Domain</Label>
                  <Select value={form.domain_id} onValueChange={(v) => setForm({ ...form, domain_id: v })}>
                    <SelectTrigger data-testid="alias-domain-select"><SelectValue placeholder="Select domain" /></SelectTrigger>
                    <SelectContent>
                      {domains.map((d) => <SelectItem key={d.id} value={d.id}>{d.name}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>Forward to (comma or space separated)</Label>
                  <Input value={form.destinations}
                         onChange={(e) => setForm({ ...form, destinations: e.target.value })}
                         placeholder="me@gmail.com, team@company.com" required
                         data-testid="alias-destinations-input" />
                </div>
                <DialogFooter><Button type="submit" data-testid="alias-submit">Create</Button></DialogFooter>
              </form>
            </DialogContent>
          </Dialog>
        }
      />

      <Card className="rounded-md border border-border overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Alias</TableHead>
              <TableHead>Destinations</TableHead>
              <TableHead>Type</TableHead>
              <TableHead>Enabled</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody data-testid="aliases-table-body">
            {items.length === 0 && (
              <TableRow><TableCell colSpan={5} className="text-center text-muted-foreground py-10">
                {domains.length === 0 ? "Add a domain first to create aliases." : "No aliases yet."}
              </TableCell></TableRow>
            )}
            {items.map((a) => (
              <TableRow key={a.id}>
                <TableCell className="font-mono">{a.address}</TableCell>
                <TableCell className="font-mono text-xs">
                  <div className="flex items-center gap-1.5 flex-wrap">
                    {a.destinations.map((d) => (
                      <span key={d} className="inline-flex items-center gap-1">
                        <ArrowRight className="h-3 w-3 text-muted-foreground" /> {d}
                      </span>
                    ))}
                  </div>
                </TableCell>
                <TableCell>
                  {a.catch_all ? <Badge variant="outline" className="text-violet-500 border-violet-500/40">catch-all</Badge>
                   : <Badge variant="outline">forward</Badge>}
                </TableCell>
                <TableCell>
                  <Switch checked={a.enabled} onCheckedChange={(v) => toggle(a.id, v)} data-testid={`toggle-${a.address}`} />
                </TableCell>
                <TableCell className="text-right">
                  <Button variant="ghost" size="sm" onClick={() => remove(a.id)} data-testid={`delete-alias-${a.address}`}>
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
