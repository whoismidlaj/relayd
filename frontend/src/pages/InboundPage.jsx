import React, { useEffect, useState } from "react";
import AppShell, { PageHeader } from "@/components/AppShell";
import { api, formatApiError } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Mail, Trash2, Clock, User, Hash, Inbox, Reply, Forward, Archive, Tag, ChevronLeft } from "lucide-react";
import { toast } from "sonner";
import { ScrollArea } from "@/components/ui/scroll-area";

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
    <AppShell fullWidth={true}>
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

      <div className="flex flex-col md:flex-row h-[calc(100vh-12rem)] md:h-[calc(100vh-15rem)] border border-border rounded-xl overflow-hidden bg-background shadow-sm relative">
        {/* Left List Pane */}
        <div className={`
          w-full md:w-1/3 border-r border-border flex flex-col bg-muted/10 md:min-w-[320px] h-full
          ${selected ? 'hidden md:flex' : 'flex'}
        `}>
          <div className="p-4 border-b border-border bg-background/50 flex items-center justify-between shrink-0">
            <h3 className="font-semibold flex items-center gap-2"><Inbox className="h-4 w-4" /> Unified Inbox</h3>
            <Badge variant="secondary" className="font-mono text-[10px]">{stats.total} total</Badge>
          </div>
          <ScrollArea className="flex-1">
            {messages.length === 0 && !loading && (
              <div className="p-10 text-center text-muted-foreground flex flex-col items-center">
                <Mail className="h-8 w-8 mb-3 opacity-20" />
                <p className="text-sm">Inbox is empty</p>
              </div>
            )}
            <div className="divide-y divide-border">
              {messages.map((m) => {
                const aliasTag = m.to.split("@")[0];
                return (
                  <div 
                    key={m.id} 
                    className={`p-4 cursor-pointer transition-all hover:bg-muted/50 border-l-2 ${selected?.id === m.id ? 'bg-muted/50 border-primary' : 'border-transparent'} ${m.read ? 'opacity-70' : 'bg-primary/5'}`}
                    onClick={() => openMessage(m)}
                  >
                    <div className="flex items-center justify-between mb-1.5">
                      <div className="font-medium text-sm truncate pr-2" title={m.from}>{m.from.split("<")[0] || m.from}</div>
                      <div className="text-xs text-muted-foreground whitespace-nowrap">{new Date(m.created_at).toLocaleDateString()}</div>
                    </div>
                    <div className="font-semibold text-sm mb-1.5 truncate">{m.subject}</div>
                    <div className="flex items-center gap-2">
                      {!m.read && <div className="h-2 w-2 rounded-full bg-primary shrink-0" />}
                      <Badge variant="outline" className="text-[10px] px-1.5 py-0 h-4 bg-background"><Tag className="h-2.5 w-2.5 mr-1" /> {aliasTag}</Badge>
                    </div>
                  </div>
                );
              })}
            </div>
          </ScrollArea>
        </div>

        {/* Right Reading Pane */}
        <div className={`
          w-full md:w-2/3 flex flex-col bg-background relative h-full
          ${selected ? 'flex' : 'hidden md:flex'}
        `}>
          {selected ? (
            <>
              <div className="p-4 md:p-5 border-b border-border bg-muted/5 flex flex-col md:flex-row md:items-start justify-between gap-4 shrink-0">
                <div className="flex flex-col min-w-0">
                  <div className="flex items-center gap-2 mb-3 md:hidden">
                    <Button variant="ghost" size="sm" className="-ml-2 h-8 px-2" onClick={() => setSelected(null)}>
                      <ChevronLeft className="h-4 w-4 mr-1" /> Back
                    </Button>
                  </div>
                  <h2 className="text-lg md:text-xl font-semibold mb-3 md:mb-4 pr-10 truncate">{selected.subject}</h2>
                  <div className="space-y-1.5 text-xs md:text-sm">
                    <div className="flex items-center gap-2"><User className="h-3 w-3 md:h-4 md:w-4 text-muted-foreground" /> <span className="font-medium truncate">{selected.from}</span></div>
                    <div className="flex items-center gap-2"><Hash className="h-3 w-3 md:h-4 md:w-4 text-muted-foreground" /> <span className="text-muted-foreground shrink-0">to</span> <Badge variant="secondary" className="text-[10px] md:text-xs py-0 h-5 truncate">{selected.to}</Badge></div>
                    <div className="flex items-center gap-2"><Clock className="h-3 w-3 md:h-4 md:w-4 text-muted-foreground" /> <span className="text-muted-foreground shrink-0">{new Date(selected.created_at).toLocaleString()}</span></div>
                  </div>
                </div>
                <div className="flex gap-2 self-end md:self-start">
                  <Button variant="outline" size="sm" className="h-8 w-8 md:h-9 md:w-9 p-0"><Reply className="h-4 w-4" /></Button>
                  <Button variant="outline" size="sm" className="h-8 w-8 md:h-9 md:w-9 p-0" onClick={(e) => { deleteMessage(selected.id, e); setSelected(null); }}><Trash2 className="h-4 w-4 text-destructive" /></Button>
                </div>
              </div>
              <ScrollArea className="flex-1 p-4 md:p-6 bg-white dark:bg-zinc-950">
                {selected.body_html ? (
                  <iframe 
                    title="email-content"
                    className="w-full min-h-[500px] border-none rounded-md bg-white"
                    srcDoc={selected.body_html}
                    sandbox="allow-popups allow-popups-to-escape-sandbox allow-same-origin"
                  />
                ) : (
                  <pre className="whitespace-pre-wrap font-sans text-xs md:text-sm text-foreground bg-muted/30 p-4 md:p-6 rounded-lg border border-border">
                    {selected.body_text}
                  </pre>
                )}
              </ScrollArea>
            </>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center text-muted-foreground">
              <Inbox className="h-12 w-12 mb-4 opacity-10" />
              <p>Select a message to read</p>
            </div>
          )}
        </div>
      </div>
    </AppShell>
  );
}
