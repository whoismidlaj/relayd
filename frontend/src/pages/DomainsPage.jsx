import React, { useEffect, useState } from "react";
import AppShell, { PageHeader, SectionLabel } from "@/components/AppShell";
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
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { Plus, Trash2, ExternalLink, RefreshCw, Pencil } from "lucide-react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { DialogDescription } from "@/components/ui/dialog";

export default function DomainsPage() {
  const [domains, setDomains] = useState([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [name, setName] = useState("");
  const [selector, setSelector] = useState("mail");
  const [mailHost, setMailHost] = useState("mail");
  const [verifying, setVerifying] = useState(null);

  const refresh = async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/domains");
      setDomains(data);
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { refresh(); }, []);

  const saveDomain = async (e) => {
    e.preventDefault();
    try {
      if (editingId) {
        await api.patch(`/domains/${editingId}`, { dkim_selector: selector, mail_host: mailHost });
        toast.success(`Domain ${name} updated`);
      } else {
        await api.post("/domains", { name, dkim_selector: selector, mail_host: mailHost });
        toast.success(`Domain ${name} added`);
      }
      setOpen(false);
      setEditingId(null);
      setName(""); setSelector("mail"); setMailHost("mail");
      refresh();
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail));
    }
  };

  const startEdit = (d) => {
    setEditingId(d.id);
    setName(d.name);
    setSelector(d.dkim_selector);
    setMailHost(d.mail_host);
    setOpen(true);
  };

  const startAdd = () => {
    setEditingId(null);
    setName("");
    setSelector("mail");
    setMailHost("mail");
    setOpen(true);
  };

  const removeDomain = async (id, dn) => {
    if (!confirm(`Delete ${dn}? This also removes its mailboxes and aliases.`)) return;
    try {
      await api.delete(`/domains/${id}`);
      toast.success("Domain removed");
      refresh();
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail));
    }
  };

  const verifyDomain = async (id) => {
    setVerifying(id);
    try {
      const { data } = await api.post(`/domains/${id}/verify`);
      toast.success(`Verified — score ${data.score}/100`);
      refresh();
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail));
    } finally {
      setVerifying(null);
    }
  };

  return (
    <AppShell>
      <PageHeader
        title="Domains"
        description="Add the domains you want to send/receive mail with. We auto-generate SPF, DKIM, DMARC and MX records."
        testId="domains-header"
        actions={
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
              <Button onClick={startAdd} data-testid="add-domain-button"><Plus className="h-4 w-4" /> Add domain</Button>
            </DialogTrigger>
            <DialogContent data-testid="add-domain-dialog">
              <DialogHeader>
                <DialogTitle>{editingId ? "Edit domain" : "Add a new domain"}</DialogTitle>
                <DialogDescription>Configure DKIM and Mail Host settings for your domain. Note: The domain name itself cannot be changed after creation.</DialogDescription>
              </DialogHeader>
              <form onSubmit={saveDomain} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="dn">Domain name</Label>
                  <Input id="dn" placeholder="example.com" required value={name}
                         onChange={(e) => setName(e.target.value)}
                         disabled={!!editingId}
                         data-testid="add-domain-name-input" />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-2">
                    <Label htmlFor="sel">DKIM selector</Label>
                    <Input id="sel" value={selector} onChange={(e) => setSelector(e.target.value)}
                           data-testid="add-domain-selector-input" />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="mh">Mail host prefix</Label>
                    <Input id="mh" value={mailHost} onChange={(e) => setMailHost(e.target.value)}
                           data-testid="add-domain-host-input" />
                  </div>
                </div>
                <DialogFooter>
                  <Button type="submit" data-testid="add-domain-submit">{editingId ? "Update domain" : "Create domain"}</Button>
                </DialogFooter>
              </form>
            </DialogContent>
          </Dialog>
        }
      />

      <Card className="rounded-md border border-border overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Domain</TableHead>
              <TableHead className="hidden md:table-cell">Selector</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Score</TableHead>
              <TableHead className="hidden lg:table-cell">Last check</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody data-testid="domains-table-body">
            {loading && (
              <TableRow><TableCell colSpan={6} className="text-center text-muted-foreground py-10">Loading…</TableCell></TableRow>
            )}
            {!loading && domains.length === 0 && (
              <TableRow><TableCell colSpan={6} className="text-center text-muted-foreground py-10">
                No domains yet. Click <span className="font-mono">Add domain</span> to get started.
              </TableCell></TableRow>
            )}
            {domains.map((d) => (
              <TableRow key={d.id} data-testid={`domain-row-${d.name}`}>
                <TableCell className="font-mono">{d.name}</TableCell>
                <TableCell className="font-mono text-xs text-muted-foreground hidden md:table-cell">{d.dkim_selector}</TableCell>
                <TableCell>
                  <Badge variant="outline" className={d.verified ? "text-emerald-500 border-emerald-500/40" : "text-amber-500 border-amber-500/40"}>
                    {d.verified ? "verified" : "pending"}
                  </Badge>
                </TableCell>
                <TableCell className="font-mono">{d.score ?? 0}/100</TableCell>
                <TableCell className="font-mono text-xs text-muted-foreground hidden lg:table-cell">
                  {d.last_checked_at ? new Date(d.last_checked_at).toLocaleString() : "—"}
                </TableCell>
                <TableCell className="text-right space-x-1">
                  <Button variant="ghost" size="sm" onClick={() => startEdit(d)} data-testid={`edit-${d.name}`}>
                    <Pencil className="h-3.5 w-3.5" />
                  </Button>
                  <Button variant="ghost" size="sm" onClick={() => verifyDomain(d.id)}
                          disabled={verifying === d.id} data-testid={`verify-${d.name}`}>
                    <RefreshCw className={`h-3.5 w-3.5 ${verifying === d.id ? "animate-spin" : ""}`} />
                    Verify
                  </Button>
                  <Link to={`/domains/${d.id}`}>
                    <Button variant="ghost" size="sm" data-testid={`open-${d.name}`}>
                      <ExternalLink className="h-3.5 w-3.5" /> Records
                    </Button>
                  </Link>
                  <Button variant="ghost" size="sm" onClick={() => removeDomain(d.id, d.name)}
                          data-testid={`delete-${d.name}`}>
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
