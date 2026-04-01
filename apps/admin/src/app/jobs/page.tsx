import { fetchAPI } from '@/lib/api';

interface ScrapeJob {
  id: string;
  portalName: string;
  status: string;
  scraped: number;
  new: number;
  errors: number;
  startedAt: string | null;
  duration: number | null;
}

async function getJobs(): Promise<ScrapeJob[]> {
  try {
    return await fetchAPI('/scrape-jobs');
  } catch {
    return [];
  }
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
                <th className="px-6 py-3 font-medium">Scraped</th>
                <th className="px-6 py-3 font-medium">Nuevos</th>
                <th className="px-6 py-3 font-medium">Errores</th>
                <th className="px-6 py-3 font-medium">Inicio</th>
                <th className="px-6 py-3 font-medium">Duracion</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {jobs.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-6 py-8 text-center text-muted-foreground">
                    No hay jobs registrados
                  </td>
                </tr>
              ) : (
                jobs.map((job) => (
                  <tr key={job.id}>
                    <td className="px-6 py-3 font-medium">{job.portalName}</td>
                    <td className="px-6 py-3">
                      <JobStatusBadge status={job.status} />
                    </td>
                    <td className="px-6 py-3">{job.scraped.toLocaleString()}</td>
                    <td className="px-6 py-3">{job.new.toLocaleString()}</td>
                    <td className="px-6 py-3">
                      {job.errors > 0 ? (
                        <span className="text-red-400">{job.errors}</span>
                      ) : (
                        job.errors
                      )}
                    </td>
                    <td className="px-6 py-3 text-muted-foreground">
                      {job.startedAt ? new Date(job.startedAt).toLocaleString('es-MX', { dateStyle: 'short', timeStyle: 'short' }) : '—'}
                    </td>
                    <td className="px-6 py-3 text-muted-foreground">
                      {job.duration != null ? formatDuration(job.duration) : '—'}
                    </td>
                  </tr>
                ))
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
