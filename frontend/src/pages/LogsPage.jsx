import React, { useEffect, useState } from "react";
import AppShell, { PageHeader } from "@/components/AppShell";
import { api, formatApiError } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger,
} from "@/components/ui/dialog";
import { RotateCcw, Trash2, Eye } from "lucide-react";
import { toast } from "sonner";

export default function LogsPage() {
  const [items, setItems] = useState([]);
  const [open, setOpen] = useState(null);

  const refresh = async () => {
    try {
      const { data } = await api.get("/logs");
      setItems(data);
    } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
  };

  useEffect(() => { refresh(); }, []);

  const retry = async (id) => {
    try {
      await api.post(`/logs/${id}/retry`);
      toast.success("Retry queued");
      refresh();
    } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
  };

  const remove = async (id) => {
    try { await api.delete(`/logs/${id}`); refresh(); }
    catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
  };

  return (
    <AppShell>
      <PageHeader title="Delivery logs"
        description="Every test or queued outbound send produces a log entry with full provider response and retry chain."
        testId="logs-header"
        actions={<Button variant="outline" onClick={refresh} data-testid="refresh-logs-button">Refresh</Button>}
      />

      <Card className="rounded-md border border-border overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Time</TableHead>
              <TableHead>To</TableHead>
              <TableHead className="hidden lg:table-cell">Provider</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody data-testid="logs-table-body">
            {items.length === 0 && (
              <TableRow><TableCell colSpan={6} className="text-center text-muted-foreground py-10">
                No delivery logs yet.
              </TableCell></TableRow>
            )}
            {items.map((l) => (
              <TableRow key={l.id}>
                <TableCell className="font-mono text-xs whitespace-nowrap text-muted-foreground">
                  {new Date(l.created_at).toLocaleString()}
                </TableCell>
                <TableCell className="font-mono text-xs">{l.to}</TableCell>
                <TableCell className="text-xs hidden lg:table-cell">{l.provider_name || "—"}</TableCell>
                <TableCell>
                  <Badge variant="outline" className={l.status === "sent" ? "text-emerald-500 border-emerald-500/40" : "text-destructive border-destructive/40"}>
                    {l.status}
                  </Badge>
                </TableCell>
                <TableCell className="text-right space-x-1">
                  <Dialog open={open === l.id} onOpenChange={(o) => setOpen(o ? l.id : null)}>
                    <DialogTrigger asChild>
                      <Button size="sm" variant="ghost" data-testid={`view-log-${l.id}`}><Eye className="h-3.5 w-3.5" /></Button>
                    </DialogTrigger>
                    <DialogContent className="max-h-[80vh] overflow-y-auto">
                      <DialogHeader><DialogTitle>Delivery details</DialogTitle></DialogHeader>
                      <pre className="dns-code bg-muted/40 border border-border rounded-sm p-3 text-xs whitespace-pre-wrap">
{JSON.stringify(
  Object.fromEntries(Object.entries(l).filter(([k]) => !['subject', 'body_text', 'body_html', 'headers'].includes(k))), 
  null, 
  2
)}
                      </pre>
                    </DialogContent>
                  </Dialog>
                  {l.status === "failed" && (
                    <Button size="sm" variant="ghost" onClick={() => retry(l.id)} data-testid={`retry-${l.id}`}>
                      <RotateCcw className="h-3.5 w-3.5" />
                    </Button>
                  )}
                  <Button size="sm" variant="ghost" onClick={() => remove(l.id)} data-testid={`delete-log-${l.id}`}>
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
