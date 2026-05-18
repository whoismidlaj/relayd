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
import { Trash2, Eye } from "lucide-react";
import { toast } from "sonner";

export default function InboundPage() {
  const [messages, setMessages] = useState([]);
  const [open, setOpen] = useState(null);

  const refresh = async () => {
    try {
      const { data } = await api.get("/inbound/messages");
      setMessages(data);
    } catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
  };

  useEffect(() => { refresh(); }, []);

  const remove = async (id) => {
    if (!confirm("Delete this inbound log?")) return;
    try { 
      await api.delete(`/inbound/messages/${id}`); 
      refresh(); 
      toast.success("Log deleted");
    }
    catch (e) { toast.error(formatApiError(e.response?.data?.detail)); }
  };

  return (
    <AppShell>
      <PageHeader title="Inbound Logs"
        description="A log of all emails successfully received and processed by your inbound routing."
        testId="inbound-logs-header"
        actions={<Button variant="outline" onClick={refresh} data-testid="refresh-inbound-logs-button">Refresh</Button>}
      />

      <Card className="rounded-md border border-border overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Time</TableHead>
              <TableHead>From</TableHead>
              <TableHead>To</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody data-testid="inbound-logs-table-body">
            {messages.length === 0 && (
              <TableRow><TableCell colSpan={5} className="text-center text-muted-foreground py-10">
                No inbound emails received yet.
              </TableCell></TableRow>
            )}
            {messages.map((m) => (
              <TableRow key={m.id}>
                <TableCell className="font-mono text-xs whitespace-nowrap text-muted-foreground">
                  {new Date(m.created_at).toLocaleString()}
                </TableCell>
                <TableCell className="text-xs truncate max-w-[200px]">{m.from}</TableCell>
                <TableCell className="font-mono text-xs max-w-[200px] truncate">
                  <Badge variant="secondary" className="font-mono text-[10px] truncate max-w-[180px]">
                    {m.to}
                  </Badge>
                </TableCell>
                <TableCell className="text-right space-x-1">
                  <Dialog open={open === m.id} onOpenChange={(o) => setOpen(o ? m.id : null)}>
                    <DialogTrigger asChild>
                      <Button size="sm" variant="ghost" data-testid={`view-inbound-${m.id}`}><Eye className="h-3.5 w-3.5" /></Button>
                    </DialogTrigger>
                    <DialogContent className="max-w-md max-h-[80vh] overflow-y-auto">
                      <DialogHeader><DialogTitle>Inbound Delivery Details</DialogTitle></DialogHeader>
                      <div className="space-y-4">
                        <div className="grid grid-cols-1 gap-2 text-sm bg-muted/30 p-4 rounded-md border border-border">
                          <div><span className="font-semibold text-muted-foreground w-16 inline-block">Date:</span> {new Date(m.created_at).toLocaleString()}</div>
                          <div><span className="font-semibold text-muted-foreground w-16 inline-block">From:</span> {m.from}</div>
                          <div><span className="font-semibold text-muted-foreground w-16 inline-block">To:</span> {m.to}</div>
                          <div><span className="font-semibold text-muted-foreground w-16 inline-block">Mailbox:</span> {m.is_mailbox ? "Yes" : "No"}</div>
                        </div>
                      </div>
                    </DialogContent>
                  </Dialog>
                  <Button size="sm" variant="ghost" onClick={() => remove(m.id)} data-testid={`delete-inbound-${m.id}`}>
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
