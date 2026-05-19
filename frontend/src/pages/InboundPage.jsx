import React, { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import AppShell, { PageHeader } from "@/components/AppShell";
import { api, formatApiError } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/lib/auth";
import ComposeDialog from "@/components/ComposeDialog";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger,
} from "@/components/ui/dialog";
import { 
  Trash2, Eye, Inbox, Send, AlertTriangle, Search, Plus, 
  RefreshCw, Mail, MailOpen, User, Clock, ArrowRight, ShieldAlert
} from "lucide-react";
import { toast } from "sonner";

export default function InboundPage() {
  const { user } = useAuth();
  const [searchParams] = useSearchParams();
  const [messages, setMessages] = useState([]);
  const [sentMessages, setSentMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [composeOpen, setComposeOpen] = useState(false);

  const currentFolder = searchParams.get("folder") || "inbox"; // inbox, sent, spam, trash
  const [selectedMessage, setSelectedMessage] = useState(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [adminOpenId, setAdminOpenId] = useState(null);

  const refreshData = async () => {
    if (!user) return;
    setLoading(true);
    try {
      if (user.role === "mailbox") {
        // Fetch directly from Dovecot via IMAP — pass folder so server fetches the right mailbox
        const folderParam = currentFolder === "sent" ? "sent" : currentFolder;
        const resInbound = await api.get(`/inbound/messages?folder=${folderParam}&limit=100`);
        setMessages(resInbound.data);
        setSentMessages([]);
      } else {
        // Admin view: inbound logs metadata
        const resInbound = await api.get("/inbound/messages");
        setMessages(resInbound.data);
      }
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refreshData();
  }, [user, currentFolder]); // re-fetch when folder changes

  // Reset selected message when folder changes
  useEffect(() => {
    setSelectedMessage(null);
  }, [currentFolder]);

  // Broadcast unread count updates to sidebar
  useEffect(() => {
    if (user?.role === "mailbox") {
      window.dispatchEvent(new Event("relayd-mail-updated"));
    }
  }, [messages, user]);

  // Folder Actions — all server-side via IMAP move
  const moveToTrash = async (id) => {
    try {
      await api.post(`/inbound/messages/${id}/move?src=${currentFolder}&dst=trash`);
      setMessages(prev => prev.filter(m => m.id !== id));
      if (selectedMessage?.id === id) setSelectedMessage(null);
      toast.success("Message moved to Trash");
    } catch (e) {
      toast.error("Failed to move to Trash");
    }
  };

  const moveToSpam = async (id) => {
    try {
      await api.post(`/inbound/messages/${id}/move?src=${currentFolder}&dst=spam`);
      setMessages(prev => prev.filter(m => m.id !== id));
      if (selectedMessage?.id === id) setSelectedMessage(null);
      toast.success("Message marked as Spam");
    } catch (e) {
      toast.error("Failed to mark as Spam");
    }
  };

  const restoreFromSpam = async (id) => {
    try {
      await api.post(`/inbound/messages/${id}/move?src=spam&dst=inbox`);
      setMessages(prev => prev.filter(m => m.id !== id));
      if (selectedMessage?.id === id) setSelectedMessage(null);
      toast.success("Message restored to Inbox");
    } catch (e) {
      toast.error("Failed to restore message");
    }
  };

  const restoreFromTrash = async (id) => {
    try {
      await api.post(`/inbound/messages/${id}/move?src=trash&dst=inbox`);
      setMessages(prev => prev.filter(m => m.id !== id));
      if (selectedMessage?.id === id) setSelectedMessage(null);
      toast.success("Message restored to Inbox");
    } catch (e) {
      toast.error("Failed to restore message");
    }
  };

  const permanentlyDelete = async (id) => {
    if (!confirm("Are you sure you want to permanently delete this message?")) return;
    try {
      await api.delete(`/inbound/messages/${id}?folder=${currentFolder}`);
      setMessages(prev => prev.filter(m => m.id !== id));
      if (selectedMessage?.id === id) setSelectedMessage(null);
      toast.success("Message permanently deleted");
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail));
    }
  };

  const markAsRead = async (msg) => {
    if (msg.read) return;
    try {
      // Fetching the full message marks it as read server-side (\Seen flag)
      await api.get(`/inbound/messages/${msg.id}?folder=${currentFolder}`);
      setMessages(prev => prev.map(m => m.id === msg.id ? { ...m, read: true } : m));
    } catch (e) {
      console.error("Failed to mark as read", e);
    }
  };

  const selectEmail = async (msg) => {
    // If we only have a preview, fetch the full body on click
    if (!msg.body_text && !msg.body_html && msg.id) {
      try {
        const res = await api.get(`/inbound/messages/${msg.id}?folder=${currentFolder}`);
        const full = res.data;
        setSelectedMessage(full);
        setMessages(prev => prev.map(m => m.id === msg.id ? { ...m, read: true } : m));
        return;
      } catch (e) {
        // fallback to preview
      }
    }
    setSelectedMessage(msg);
    if (msg.to && !msg.read) markAsRead(msg);
  };

  // Filter (client-side search on the already-fetched folder)
  const getFilteredEmails = () => {
    return messages.filter(m => {
      const term = searchQuery.toLowerCase();
      return (
        (m.from || "").toLowerCase().includes(term) ||
        (m.to || "").toLowerCase().includes(term) ||
        (m.subject || "").toLowerCase().includes(term) ||
        (m.body || "").toLowerCase().includes(term)
      );
    });
  };

  const filteredEmails = getFilteredEmails();

  // -----------------------------------------------------------
  // RENDER METHOD A: MAILBOX USER (PREMIUM TWO-PANE WEBMAIL)
  // -----------------------------------------------------------
  if (user?.role === "mailbox") {
    return (
      <AppShell fullWidth={true}>
        <div className="flex h-[calc(100vh-80px)] -m-4 md:-m-6 overflow-hidden rounded-lg border border-border bg-background shadow-lg">
          
          {/* 1. Left Pane: Email List View */}
          <section className="w-80 border-r border-border flex flex-col bg-background shrink-0">
            <div className="p-3 border-b border-border space-y-2">
              <div className="flex items-center gap-2">
                <div className="relative flex-1">
                  <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                  <Input
                    placeholder="Search emails..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="pl-8 h-9 text-xs"
                  />
                </div>
                <Button 
                  variant="outline" 
                  size="icon" 
                  onClick={refreshData} 
                  disabled={loading}
                  title="Sync Mailbox"
                  className="h-9 w-9 shrink-0 text-muted-foreground hover:text-foreground"
                >
                  <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
                </Button>
              </div>
              <div className="text-[10px] font-bold text-muted-foreground uppercase tracking-[0.12em] px-1 flex items-center justify-between">
                <span>{currentFolder} folder</span>
                <span>{filteredEmails.length} messages</span>
              </div>
            </div>

            <div className="flex-1 overflow-y-auto divide-y divide-border/60">
              {loading && (
                <div className="flex flex-col items-center justify-center p-8 text-center text-muted-foreground">
                  <RefreshCw className="h-6 w-6 mb-2 animate-spin opacity-50" />
                  <p className="text-xs">Loading from server...</p>
                </div>
              )}

              {!loading && filteredEmails.length === 0 && (
                <div className="flex flex-col items-center justify-center p-8 text-center text-muted-foreground">
                  <Mail className="h-8 w-8 mb-2 stroke-1 opacity-40 animate-pulse" />
                  <p className="text-xs font-semibold">No emails here</p>
                  <p className="text-[10px] text-muted-foreground/80 mt-0.5">Your folder is completely clean!</p>
                </div>
              )}

              {!loading && filteredEmails.map((msg) => {

                const isSent = currentFolder === "sent";
                const senderLabel = isSent ? `To: ${msg.to_email}` : msg.from;
                const dateStr = new Date(msg.created_at).toLocaleDateString(undefined, {
                  month: "short",
                  day: "numeric"
                });
                
                return (
                  <div
                    key={msg.id}
                    onClick={() => selectEmail(msg)}
                    className={`p-3.5 cursor-pointer transition-all hover:bg-muted/40 select-none ${
                      selectedMessage?.id === msg.id ? "bg-primary/5 border-l-4 border-primary pl-2.5" : "pl-3.5"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-1 mb-1">
                      <span className={`text-xs font-bold truncate max-w-[140px] ${
                        !isSent && !msg.read ? "text-foreground font-black" : "text-muted-foreground"
                      }`}>
                        {senderLabel}
                      </span>
                      <span className="text-[10px] text-muted-foreground whitespace-nowrap">
                        {dateStr}
                      </span>
                    </div>

                    <h4 className={`text-xs truncate ${
                      !isSent && !msg.read ? "font-bold text-foreground" : "text-muted-foreground/90 font-medium"
                    }`}>
                      {msg.subject || "(No Subject)"}
                    </h4>

                    <p className="text-[11px] text-muted-foreground/75 truncate mt-1">
                      {msg.body || "No preview available"}
                    </p>

                    <div className="flex items-center gap-1.5 mt-2">
                      {!isSent && !msg.read && (
                        <span className="h-1.5 w-1.5 rounded-full bg-primary" />
                      )}
                      {msg.tags && msg.tags.map((tag, idx) => (
                        <Badge key={idx} variant="outline" className="text-[8px] px-1 py-0 h-4 border-primary/20 bg-primary/5 text-primary">
                          {tag}
                        </Badge>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          </section>

          {/* 2. Right Pane: Reading Pane */}
          <main className="flex-1 bg-muted/5 flex flex-col overflow-hidden">
            {selectedMessage ? (
              <div className="flex-1 flex flex-col overflow-hidden">
                {/* Message Header Bar */}
                <div className="p-4 border-b border-border bg-background flex items-center justify-between shrink-0">
                  <div className="flex items-center gap-2">
                    {currentFolder === "inbox" && (
                      <>
                        <Button 
                          variant="ghost" 
                          size="icon" 
                          onClick={() => moveToSpam(selectedMessage.id)} 
                          title="Mark as Spam"
                          className="h-8 w-8 text-muted-foreground hover:text-warning"
                        >
                          <ShieldAlert className="h-4 w-4" />
                        </Button>
                        <Button 
                          variant="ghost" 
                          size="icon" 
                          onClick={() => moveToTrash(selectedMessage.id)} 
                          title="Move to Trash"
                          className="h-8 w-8 text-muted-foreground hover:text-destructive"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </>
                    )}

                    {currentFolder === "spam" && (
                      <Button 
                        variant="outline" 
                        size="sm" 
                        onClick={() => restoreFromSpam(selectedMessage.id)}
                        className="h-8 text-xs gap-1.5"
                      >
                        Not Spam
                      </Button>
                    )}

                    {currentFolder === "trash" && (
                      <>
                        <Button 
                          variant="outline" 
                          size="sm" 
                          onClick={() => restoreFromTrash(selectedMessage.id)}
                          className="h-8 text-xs gap-1.5"
                        >
                          Restore
                        </Button>
                        <Button 
                          variant="destructive" 
                          size="sm" 
                          onClick={() => permanentlyDelete(selectedMessage.id, currentFolder !== "sent")}
                          className="h-8 text-xs gap-1.5"
                        >
                          Delete Permanently
                        </Button>
                      </>
                    )}
                  </div>
                </div>

                {/* Main Email Content */}
                <div className="flex-1 overflow-y-auto p-6 space-y-6 bg-background">
                  <div>
                    <h1 className="text-xl font-bold tracking-tight text-foreground">
                      {selectedMessage.subject || "(No Subject)"}
                    </h1>
                    
                    <div className="flex flex-wrap gap-1 mt-2">
                      {selectedMessage.tags && selectedMessage.tags.map((t, idx) => (
                        <Badge key={idx} variant="outline" className="text-[10px] border-primary/30 text-primary bg-primary/5">
                          {t}
                        </Badge>
                      ))}
                    </div>
                  </div>

                  {/* Sender Details */}
                  <div className="flex items-center gap-3 p-3 rounded-lg border border-border bg-muted/10">
                    <div className="h-10 w-10 rounded-full bg-primary/10 text-primary grid place-items-center font-bold text-sm shrink-0">
                      <User className="h-4 w-4" />
                    </div>
                    
                    <div className="flex-1 min-w-0 text-xs space-y-0.5">
                      <div className="flex items-center justify-between">
                        <span className="font-semibold text-foreground truncate block">
                          {currentFolder === "sent" ? "To: " + selectedMessage.to_email : "From: " + selectedMessage.from}
                        </span>
                        <span className="text-[10px] text-muted-foreground flex items-center gap-1">
                          <Clock className="h-3 w-3" /> {new Date(selectedMessage.created_at).toLocaleString()}
                        </span>
                      </div>
                      <div className="text-muted-foreground truncate">
                        {currentFolder === "sent" ? "From: " + selectedMessage.from_email : "To: " + selectedMessage.to}
                      </div>
                    </div>
                  </div>

                  {/* Message Body */}
                  <div className="border border-border/80 rounded-lg p-6 bg-muted/5 min-h-[300px] text-sm leading-relaxed text-foreground whitespace-pre-wrap font-sans">
                    {selectedMessage.body || "This email has no text content."}
                  </div>
                </div>
              </div>
            ) : (
              <div className="flex-1 flex flex-col items-center justify-center text-center text-muted-foreground p-8">
                <div className="h-16 w-16 rounded-full bg-muted/40 grid place-items-center mb-4 border border-dashed border-border">
                  <Mail className="h-8 w-8 stroke-1 opacity-60 text-primary/60" />
                </div>
                <h3 className="text-sm font-semibold">No Email Selected</h3>
                <p className="text-xs max-w-xs mt-1 text-muted-foreground/85 leading-relaxed">
                  Choose a folder from your sidebar and select an email to view its content.
                </p>
              </div>
            )}
          </main>
        </div>

        <ComposeDialog open={composeOpen} onOpenChange={setComposeOpen} />
      </AppShell>
    );
  }

  // -------------------------------------------------------------
  // RENDER METHOD B: ADMINISTRATIVE USER (INBOUND LOGS)
  // -------------------------------------------------------------
  return (
    <AppShell>
      <PageHeader 
        title="Inbound Logs"
        description="A detailed orchestration log of all incoming emails routed and processed by Relayd."
        testId="inbound-logs-header"
        actions={
          <Button 
            variant="outline" 
            onClick={refreshData} 
            disabled={loading} 
            className="gap-2 shadow-sm font-medium"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            Refresh Logs
          </Button>
        }
      />

      <Card className="rounded-md border border-border overflow-hidden bg-background">
        <Table>
          <TableHeader>
            <TableRow className="bg-muted/30">
              <TableHead className="w-[180px]">Timestamp</TableHead>
              <TableHead>Sender (From)</TableHead>
              <TableHead>Recipient (To)</TableHead>
              <TableHead className="w-[100px] text-center">Mailbox</TableHead>
              <TableHead className="w-[100px] text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody data-testid="inbound-logs-table-body">
            {messages.length === 0 && (
              <TableRow>
                <TableCell colSpan={5} className="text-center text-muted-foreground py-16">
                  <div className="flex flex-col items-center justify-center space-y-2">
                    <Mail className="h-10 w-10 stroke-1 opacity-30" />
                    <span className="text-sm font-medium">No inbound emails logged yet</span>
                    <span className="text-xs text-muted-foreground/80 max-w-xs">
                      Emails received on domains mapped to Relayd will log successfully here.
                    </span>
                  </div>
                </TableCell>
              </TableRow>
            )}

            {messages.map((m) => (
              <TableRow key={m.id} className="hover:bg-muted/10">
                <TableCell className="font-mono text-[11px] whitespace-nowrap text-muted-foreground">
                  {new Date(m.created_at).toLocaleString()}
                </TableCell>
                <TableCell className="text-xs font-semibold truncate max-w-[220px]">
                  {m.from}
                </TableCell>
                <TableCell className="font-mono text-xs max-w-[220px] truncate">
                  <Badge variant="secondary" className="font-mono text-[10px] font-medium tracking-tight">
                    {m.to}
                  </Badge>
                </TableCell>
                <TableCell className="text-center">
                  <Badge variant={m.is_mailbox ? "success" : "warning"} className="text-[9px] uppercase tracking-wider px-2 font-bold h-5">
                    {m.is_mailbox ? "Mailbox" : "Relay"}
                  </Badge>
                </TableCell>
                <TableCell className="text-right space-x-1">
                  <Dialog open={adminOpenId === m.id} onOpenChange={(o) => setAdminOpenId(o ? m.id : null)}>
                    <DialogTrigger asChild>
                      <Button size="sm" variant="ghost" className="h-8 w-8 p-0" data-testid={`view-inbound-${m.id}`}>
                        <Eye className="h-4 w-4" />
                      </Button>
                    </DialogTrigger>
                    <DialogContent className="max-w-xl max-h-[85vh] overflow-y-auto rounded-lg">
                      <DialogHeader>
                        <DialogTitle className="flex items-center gap-2 text-lg font-bold">
                          <Mail className="h-5 w-5 text-primary" /> Delivery Log Details
                        </DialogTitle>
                      </DialogHeader>
                      <div className="space-y-4 py-2">
                        {/* Info Grid */}
                        <div className="grid grid-cols-2 gap-4 text-xs bg-muted/40 p-4 rounded-lg border border-border">
                          <div>
                            <span className="font-bold text-muted-foreground block mb-0.5">Timestamp:</span>
                            <span className="font-mono">{new Date(m.created_at).toLocaleString()}</span>
                          </div>
                          <div>
                            <span className="font-bold text-muted-foreground block mb-0.5">Message ID:</span>
                            <span className="font-mono truncate block">{m.id}</span>
                          </div>
                          <div className="col-span-2">
                            <span className="font-bold text-muted-foreground block mb-0.5">Sender:</span>
                            <span className="font-mono break-all">{m.from}</span>
                          </div>
                          <div className="col-span-2">
                            <span className="font-bold text-muted-foreground block mb-0.5">Recipient:</span>
                            <span className="font-mono break-all text-primary font-semibold">{m.to}</span>
                          </div>
                        </div>

                        {/* Subject */}
                        <div className="space-y-1">
                          <span className="text-xs font-bold text-muted-foreground uppercase tracking-wider block">Subject</span>
                          <div className="p-3 bg-background border border-border rounded-lg text-sm font-semibold">
                            {m.subject || "(No Subject)"}
                          </div>
                        </div>

                        {/* Message Content */}
                        <div className="space-y-1">
                          <span className="text-xs font-bold text-muted-foreground uppercase tracking-wider block">Content Body</span>
                          <div className="p-4 bg-background border border-border rounded-lg text-xs font-mono leading-relaxed whitespace-pre-wrap max-h-60 overflow-y-auto">
                            {m.body || "(Empty message content)"}
                          </div>
                        </div>
                      </div>
                    </DialogContent>
                  </Dialog>
                  
                  <Button 
                    size="sm" 
                    variant="ghost" 
                    onClick={() => permanentlyDelete(m.id, true)} 
                    className="h-8 w-8 p-0 text-destructive hover:bg-destructive/10"
                    data-testid={`delete-inbound-${m.id}`}
                  >
                    <Trash2 className="h-4 w-4" />
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
