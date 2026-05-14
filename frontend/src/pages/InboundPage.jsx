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
  Dialog, DialogContent, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { Mail, Trash2, Clock, User, Hash } from "lucide-react";
import { toast } from "sonner";

export default function InboundPage() {
  const [messages, setMessages] = useState([]);
  const [stats, setStats] = useState({ total: 0, unread: 0 });
  const [selected, setSelected] = useState(null);
  const [loading, setLoading] = useState(true);

  const refresh = async () => {
    try {
      const [msgRes, statRes] = await Promise.all([
        api.get("/inbound/messages"),
        api.get("/inbound/stats")
      ]);
      setMessages(msgRes.data);
      setStats(statRes.data);
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { refresh(); }, []);

  const openMessage = async (msg) => {
    try {
      const { data } = await api.get(`/inbound/messages/${msg.id}`);
      setSelected(data);
      if (!msg.read) refresh(); // Update unread count
    } catch (e) {
      toast.error("Could not load message details");
    }
  };

  const deleteMessage = async (id, e) => {
    e.stopPropagation();
    if (!confirm("Delete this message?")) return;
    try {
      await api.delete(`/inbound/messages/${id}`);
      toast.success("Message deleted");
      refresh();
    } catch (e) {
      toast.error("Failed to delete message");
    }
  };

  return (
    <AppShell>
      <PageHeader
        title="Inbound Messages"
        description="Emails received by your server via MX routing and Aliases."
      />

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        <Card className="p-4 flex items-center gap-4 bg-primary/5 border-primary/20">
          <div className="h-10 w-10 rounded-full bg-primary/10 flex items-center justify-center text-primary">
            <Mail className="h-5 w-5" />
          </div>
          <div>
            <p className="text-sm text-muted-foreground">Total Received</p>
            <p className="text-2xl font-bold">{stats.total}</p>
          </div>
        </Card>
        <Card className="p-4 flex items-center gap-4 bg-amber-500/5 border-amber-500/20">
          <div className="h-10 w-10 rounded-full bg-amber-500/10 flex items-center justify-center text-amber-600">
            <Mail className="h-5 w-5" />
          </div>
          <div>
            <p className="text-sm text-muted-foreground">Unread</p>
            <p className="text-2xl font-bold">{stats.unread}</p>
          </div>
        </Card>
      </div>

      <Card className="rounded-md border border-border overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>From</TableHead>
              <TableHead>To</TableHead>
              <TableHead>Subject</TableHead>
              <TableHead>Date</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {messages.length === 0 && !loading && (
              <TableRow>
                <TableCell colSpan={5} className="text-center text-muted-foreground py-20">
                  <Mail className="h-10 w-10 mx-auto mb-4 opacity-20" />
                  No messages received yet. Make sure your domain MX records point to this server.
                </TableCell>
              </TableRow>
            )}
            {messages.map((m) => (
              <TableRow 
                key={m.id} 
                className={`cursor-pointer transition-colors ${m.read ? 'opacity-70' : 'bg-primary/5 font-semibold'}`}
                onClick={() => openMessage(m)}
              >
                <TableCell className="max-w-[200px] truncate">{m.from}</TableCell>
                <TableCell className="max-w-[200px] truncate">{m.to}</TableCell>
                <TableCell className="max-w-md truncate">{m.subject}</TableCell>
                <TableCell className="text-xs text-muted-foreground whitespace-nowrap">
                  {new Date(m.created_at).toLocaleString()}
                </TableCell>
                <TableCell className="text-right">
                  <Button variant="ghost" size="sm" onClick={(e) => deleteMessage(m.id, e)}>
                    <Trash2 className="h-4 w-4 text-destructive" />
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>

      <Dialog open={!!selected} onOpenChange={() => setSelected(null)}>
        <DialogContent className="max-w-3xl max-h-[85vh] overflow-y-auto">
          {selected && (
            <>
              <DialogHeader>
                <DialogTitle className="text-xl leading-tight pr-8">{selected.subject}</DialogTitle>
                <div className="flex flex-wrap gap-4 mt-2 text-sm text-muted-foreground">
                  <div className="flex items-center gap-1.5"><User className="h-3.5 w-3.5" /> From: {selected.from}</div>
                  <div className="flex items-center gap-1.5"><Hash className="h-3.5 w-3.5" /> To: {selected.to}</div>
                  <div className="flex items-center gap-1.5"><Clock className="h-3.5 w-3.5" /> {new Date(selected.created_at).toLocaleString()}</div>
                </div>
              </DialogHeader>
              <div className="mt-6 border-t pt-6">
                {selected.body_html ? (
                  <div 
                    className="prose prose-sm dark:prose-invert max-w-none bg-white p-4 rounded-md text-black" 
                    dangerouslySetInnerHTML={{ __html: selected.body_html }} 
                  />
                ) : (
                  <pre className="whitespace-pre-wrap font-sans text-sm bg-muted p-4 rounded-md">
                    {selected.body_text}
                  </pre>
                )}
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>
    </AppShell>
  );
}
