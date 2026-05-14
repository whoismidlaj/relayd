import React, { useState } from "react";
import useSWR from "swr";
import { formatDistanceToNow } from "date-fns";
import { KeyRound, Plus, Trash2, Copy, Check } from "lucide-react";
import AppShell, { PageHeader, SectionLabel } from "@/components/AppShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";

export default function TokensPage() {
  const { data: tokens, mutate } = useSWR("/tokens");
  
  const [createOpen, setCreateOpen] = useState(false);
  const [newTokenName, setNewTokenName] = useState("");
  const [createdToken, setCreatedToken] = useState(null);
  const [copied, setCopied] = useState(false);
  const [isCreating, setIsCreating] = useState(false);

  const handleCreate = async () => {
    if (!newTokenName.trim()) return;
    setIsCreating(true);
    try {
      const res = await api.post("/tokens", { name: newTokenName.trim() });
      setCreatedToken(res.data.token);
      setNewTokenName("");
      mutate();
    } catch (err) {
      toast.error(err.response?.data?.detail || err.message);
    } finally {
      setIsCreating(false);
    }
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(createdToken);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const closeDialog = () => {
    setCreateOpen(false);
    setTimeout(() => {
      setCreatedToken(null);
      setNewTokenName("");
    }, 200);
  };

  const revokeToken = async (id) => {
    if (!confirm("Are you sure you want to revoke this API key? Any applications using it will immediately lose access.")) return;
    try {
      await api.delete(`/tokens/${id}`);
      mutate();
      toast.success("API Key Revoked");
    } catch (err) {
      toast.error(err.response?.data?.detail || err.message);
    }
  };

  return (
    <AppShell>
      <PageHeader 
        title="API Tokens" 
        description="Manage your API keys for developer integrations and automation."
        actions={
          <Button onClick={() => setCreateOpen(true)} className="gap-2">
            <Plus size={16} /> Create API Key
          </Button>
        }
      />

      <div className="space-y-6 max-w-4xl">
        <Card className="rounded-md border border-border">
          <div className="p-4 border-b border-border bg-muted/20">
            <h3 className="font-medium text-sm">Active Keys</h3>
          </div>
          
          {(!tokens || tokens.length === 0) ? (
            <div className="p-8 text-center text-muted-foreground text-sm flex flex-col items-center">
              <KeyRound className="w-12 h-12 mb-3 text-muted-foreground/30" />
              <p>No API keys generated yet.</p>
              <p className="mt-1 text-xs">Create one to start interacting with the API programmatically.</p>
            </div>
          ) : (
            <div className="divide-y divide-border">
              {tokens.map(token => (
                <div key={token.id} className="p-4 flex items-center justify-between hover:bg-muted/10 transition-colors">
                  <div>
                    <div className="font-medium flex items-center gap-2">
                      {token.name}
                      {!token.last_used_at && <Badge variant="secondary" className="text-[10px] h-4">Never used</Badge>}
                    </div>
                    <div className="text-xs text-muted-foreground flex gap-4 mt-1">
                      <span>Created {formatDistanceToNow(new Date(token.created_at))} ago</span>
                      {token.last_used_at && (
                        <span>Last used {formatDistanceToNow(new Date(token.last_used_at))} ago</span>
                      )}
                    </div>
                  </div>
                  <Button variant="ghost" size="sm" className="text-red-500 hover:text-red-600 hover:bg-red-500/10" onClick={() => revokeToken(token.id)}>
                    <Trash2 size={16} className="mr-2" /> Revoke
                  </Button>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>

      <Dialog open={createOpen} onOpenChange={closeDialog}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>{createdToken ? "API Key Created" : "Create New API Key"}</DialogTitle>
          </DialogHeader>
          
          {createdToken ? (
            <div className="space-y-4 py-4">
              <div className="bg-amber-500/10 text-amber-500 p-3 rounded-md text-sm border border-amber-500/20">
                Please copy this key and save it somewhere safe. For security reasons, <strong>we will not show it to you again</strong>.
              </div>
              <div className="flex gap-2">
                <Input value={createdToken} readOnly className="font-mono text-sm bg-muted/50" />
                <Button variant="outline" onClick={handleCopy} className="w-[100px]">
                  {copied ? <Check size={16} className="mr-2" /> : <Copy size={16} className="mr-2" />}
                  {copied ? "Copied" : "Copy"}
                </Button>
              </div>
              <DialogFooter className="mt-6">
                <Button onClick={closeDialog} className="w-full">I've saved it securely</Button>
              </DialogFooter>
            </div>
          ) : (
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">Key Name</label>
                <Input 
                  placeholder="e.g. Production Application, Zapier Integration" 
                  value={newTokenName}
                  onChange={(e) => setNewTokenName(e.target.value)}
                  autoFocus
                />
              </div>
              <DialogFooter className="mt-6">
                <Button variant="outline" onClick={closeDialog}>Cancel</Button>
                <Button onClick={handleCreate} disabled={!newTokenName.trim() || isCreating}>
                  {isCreating ? "Creating..." : "Generate Key"}
                </Button>
              </DialogFooter>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </AppShell>
  );
}
