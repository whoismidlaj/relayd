import React, { useEffect, useState } from "react";
import AppShell, { PageHeader } from "@/components/AppShell";
import { api, formatApiError } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { Activity, CheckCircle2, Clock, XCircle, AlertCircle, RefreshCw } from "lucide-react";
import { toast } from "sonner";

export default function WorkerPage() {
  const [tasks, setTasks] = useState([]);
  const [stats, setStats] = useState({ pending: 0, failed: 0, completed: 0 });
  const [loading, setLoading] = useState(true);

  const refresh = async () => {
    try {
      const [taskRes, statRes] = await Promise.all([
        api.get("/relays/tasks"),
        api.get("/relays/tasks/stats")
      ]);
      setTasks(taskRes.data);
      setStats(statRes.data);
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { refresh(); }, []);

  const getStatusBadge = (status) => {
    switch (status) {
      case "completed":
        return <Badge className="bg-green-500/10 text-green-600 hover:bg-green-500/20 border-green-500/30"><CheckCircle2 className="h-3 w-3 mr-1" /> Completed</Badge>;
      case "failed":
        return <Badge variant="destructive" className="bg-red-500/10 text-red-600 border-red-500/30"><XCircle className="h-3 w-3 mr-1" /> Failed</Badge>;
      case "processing":
        return <Badge className="bg-blue-500/10 text-blue-600 border-blue-500/30"><RefreshCw className="h-3 w-3 mr-1 animate-spin" /> Processing</Badge>;
      case "retrying":
        return <Badge className="bg-amber-500/10 text-amber-600 border-amber-500/30"><Clock className="h-3 w-3 mr-1" /> Retrying</Badge>;
      default:
        return <Badge variant="outline"><Clock className="h-3 w-3 mr-1" /> Pending</Badge>;
    }
  };

  return (
    <AppShell>
      <PageHeader
        title="Background Worker"
        description="Persistent task queue for reliable email delivery and background operations."
        actions={
          <Button variant="outline" size="sm" onClick={refresh} disabled={loading}>
            <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} /> Refresh Queue
          </Button>
        }
      />

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <Card className="p-4 flex items-center gap-4 bg-primary/5 border-primary/20">
          <div className="h-10 w-10 rounded-full bg-primary/10 flex items-center justify-center text-primary">
            <Clock className="h-5 w-5" />
          </div>
          <div>
            <p className="text-sm text-muted-foreground">Pending / Retrying</p>
            <p className="text-2xl font-bold">{stats.pending}</p>
          </div>
        </Card>
        <Card className="p-4 flex items-center gap-4 bg-green-500/5 border-green-500/20">
          <div className="h-10 w-10 rounded-full bg-green-500/10 flex items-center justify-center text-green-600">
            <CheckCircle2 className="h-5 w-5" />
          </div>
          <div>
            <p className="text-sm text-muted-foreground">Completed (Last 50)</p>
            <p className="text-2xl font-bold">{stats.completed}</p>
          </div>
        </Card>
        <Card className="p-4 flex items-center gap-4 bg-red-500/5 border-red-500/20">
          <div className="h-10 w-10 rounded-full bg-red-500/10 flex items-center justify-center text-red-600">
            <AlertCircle className="h-5 w-5" />
          </div>
          <div>
            <p className="text-sm text-muted-foreground">Failed Permanently</p>
            <p className="text-2xl font-bold">{stats.failed}</p>
          </div>
        </Card>
      </div>

      <Card className="rounded-md border border-border overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Task ID</TableHead>
              <TableHead>Type</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Attempts</TableHead>
              <TableHead>Last Run</TableHead>
              <TableHead>Error</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {tasks.length === 0 && !loading && (
              <TableRow>
                <TableCell colSpan={6} className="text-center text-muted-foreground py-20">
                  <Activity className="h-10 w-10 mx-auto mb-4 opacity-20" />
                  Task queue is currently empty.
                </TableCell>
              </TableRow>
            )}
            {tasks.map((t) => (
              <TableRow key={t.id}>
                <TableCell className="font-mono text-xs">{t.id.split('-')[0]}...</TableCell>
                <TableCell>
                  <Badge variant="outline" className="capitalize">{t.type.replace('_', ' ')}</Badge>
                </TableCell>
                <TableCell>{getStatusBadge(t.status)}</TableCell>
                <TableCell>{t.attempts || 0} / {t.max_retries || 3}</TableCell>
                <TableCell className="text-xs text-muted-foreground">
                  {new Date(t.updated_at).toLocaleString()}
                </TableCell>
                <TableCell className="max-w-[200px] truncate text-xs text-red-500">
                  {t.last_error || "-"}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>
    </AppShell>
  );
}
