import { fetchAPI } from '@/lib/api';

interface ScrapeJob {
  id: string;
  status: string;
  totalScraped: number;
  totalNew: number;
  totalUpdated: number;
  totalErrors: number;
  metadata: { mode?: string } | null;
  startedAt: string | null;
  finishedAt: string | null;
  portal: { name: string; slug: string };
}

async function getJobs(): Promise<ScrapeJob[]> {
  try {
    const res = await fetchAPI('/scrape-jobs?limit=50');
    return res.data ?? res;
  } catch {
    return [];
  }
}

function getDuration(startedAt: string | null, finishedAt: string | null): number | null {
  if (!startedAt || !finishedAt) return null;
  return Math.floor((new Date(finishedAt).getTime() - new Date(startedAt).getTime()) / 1000);
}

export default async function JobsPage() {
  const jobs = await getJobs();

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold tracking-tight">Scrape Jobs</h1>

      <div className="rounded-lg border bg-card">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-muted-foreground">
                <th className="px-6 py-3 font-medium">Portal</th>
                <th className="px-6 py-3 font-medium">Estado</th>
                <th className="px-6 py-3 font-medium">Modo</th>
                <th className="px-6 py-3 font-medium text-right">Scraped</th>
                <th className="px-6 py-3 font-medium text-right">Nuevos</th>
                <th className="px-6 py-3 font-medium text-right">Errores</th>
                <th className="px-6 py-3 font-medium">Inicio</th>
                <th className="px-6 py-3 font-medium">Duracion</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {jobs.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-6 py-8 text-center text-muted-foreground">
                    No hay jobs registrados
                  </td>
                </tr>
              ) : (
                jobs.map((job) => {
                  const duration = getDuration(job.startedAt, job.finishedAt);
                  return (
                    <tr key={job.id} className="hover:bg-muted/50">
                      <td className="px-6 py-3 font-medium">{job.portal?.name ?? '—'}</td>
                      <td className="px-6 py-3">
                        <JobStatusBadge status={job.status} />
                      </td>
                      <td className="px-6 py-3 text-muted-foreground text-xs">
                        {job.metadata?.mode ?? '—'}
                      </td>
                      <td className="px-6 py-3 text-right tabular-nums">{job.totalScraped.toLocaleString()}</td>
                      <td className="px-6 py-3 text-right tabular-nums">{job.totalNew.toLocaleString()}</td>
                      <td className="px-6 py-3 text-right">
                        {job.totalErrors > 0 ? (
                          <span className="text-red-400">{job.totalErrors}</span>
                        ) : (
                          <span className="text-muted-foreground">0</span>
                        )}
                      </td>
                      <td className="px-6 py-3 text-muted-foreground">
                        {job.startedAt
                          ? new Date(job.startedAt).toLocaleString('es-MX', { timeZone: 'America/Mexico_City', dateStyle: 'short', timeStyle: 'short' })
                          : '—'}
                      </td>
                      <td className="px-6 py-3 text-muted-foreground">
                        {duration != null ? formatDuration(duration) : '—'}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function JobStatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    completed: 'bg-green-500/10 text-green-400',
    running: 'bg-blue-500/10 text-blue-400',
    pending: 'bg-yellow-500/10 text-yellow-400',
    failed: 'bg-red-500/10 text-red-400',
    stopped_budget: 'bg-amber-500/10 text-amber-400',
  };
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-1 text-xs font-medium ${styles[status] ?? 'bg-muted text-muted-foreground'}`}>
      {status}
    </span>
  );
}

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  if (m < 60) return `${m}m ${s}s`;
  const h = Math.floor(m / 60);
  return `${h}h ${m % 60}m`;
}
