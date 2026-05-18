import React, { useState, useEffect } from "react";
import { 
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription 
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { api, formatApiError } from "@/lib/api";
import { toast } from "sonner";
import { Send, Loader2 } from "lucide-react";
import TagsInput from "@/components/TagsInput";

export default function ComposeDialog({ open, onOpenChange, defaultFrom = "" }) {
  const [mailboxes, setMailboxes] = useState([]);
  const [globalTags, setGlobalTags] = useState([]);
  const [sending, setSending] = useState(false);
  const [form, setForm] = useState({
    from_email: defaultFrom,
    to: "",
    subject: "",
    body: "",
    tags: ""
  });

  useEffect(() => {
    if (open) {
      loadMailboxes();
      loadTags();
      if (defaultFrom) {
        setForm(prev => ({ ...prev, from_email: defaultFrom }));
      }
    }
  }, [open, defaultFrom]);

  const loadTags = async () => {
    try {
      const { data } = await api.get("/tags");
      setGlobalTags(data);
    } catch (e) { console.error("Failed to load tags", e); }
  };

  const loadMailboxes = async () => {
    try {
      const { data } = await api.get("/mailboxes");
      setMailboxes(data);
      if (!form.from_email && data.length > 0) {
        setForm(prev => ({ ...prev, from_email: data[0].address }));
      }
    } catch (e) {
      console.error("Failed to load mailboxes", e);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSending(true);
    try {
      const payload = {
        ...form,
        tags: form.tags ? form.tags.split(",").map(s => s.trim()).filter(Boolean) : []
      };
      await api.post("/send/test", payload);
      toast.success("Email sent successfully!");
      onOpenChange(false);
      setForm({ from_email: defaultFrom, to: "", subject: "", body: "", tags: "" });
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail));
    } finally {
      setSending(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[550px]">
        <DialogHeader>
          <DialogTitle>Compose Email</DialogTitle>
          <DialogDescription>
            Send a new email using your Relayd mailboxes and configured relay providers.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4 py-2">
          <div className="space-y-2">
            <Label htmlFor="from">From</Label>
            <Select 
              value={form.from_email} 
              onValueChange={(v) => setForm({ ...form, from_email: v })}
            >
              <SelectTrigger id="from">
                <SelectValue placeholder="Select sender" />
              </SelectTrigger>
              <SelectContent>
                {mailboxes.map((m) => (
                  <SelectItem key={m.id} value={m.address}>
                    {m.display_name} &lt;{m.address}&gt;
                  </SelectItem>
                ))}
                {mailboxes.length === 0 && (
                  <SelectItem value={form.from_email || "no-mailbox"} disabled>
                    {form.from_email || "No mailboxes found"}
                  </SelectItem>
                )}
              </SelectContent>
            </Select>
          </div>
          
          <div className="space-y-2">
            <Label htmlFor="to">To</Label>
            <Input 
              id="to" 
              type="email" 
              placeholder="recipient@example.com" 
              required 
              value={form.to}
              onChange={(e) => setForm({ ...form, to: e.target.value })}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="subject">Subject</Label>
            <Input 
              id="subject" 
              placeholder="Enter subject" 
              required 
              value={form.subject}
              onChange={(e) => setForm({ ...form, subject: e.target.value })}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="body">Message</Label>
            <Textarea 
              id="body" 
              placeholder="Write your message here..." 
              className="min-h-[150px] resize-none"
              required 
              value={form.body}
              onChange={(e) => setForm({ ...form, body: e.target.value })}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="tags">Tags</Label>
            <TagsInput 
              value={form.tags}
              onChange={(v) => setForm({ ...form, tags: v })}
              placeholder="Add tag..."
              suggestions={globalTags}
            />
          </div>

          <DialogFooter className="pt-4">
            <Button 
              type="button" 
              variant="ghost" 
              onClick={() => onOpenChange(false)}
              disabled={sending}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={sending} className="gap-2">
              {sending ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Sending...
                </>
              ) : (
                <>
                  <Send className="h-4 w-4" />
                  Send Email
                </>
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
