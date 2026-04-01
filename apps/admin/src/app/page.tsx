import { fetchAPI } from '@/lib/api';

interface Portal {
  id: string;
  name: string;
  slug: string;
  isActive: boolean;
  avgListings: number;
  lastJobStatus: string | null;
  lastJobAt: string | null;
}

interface Stats {
  totalListings: number;
  activePortals: number;
  completedJobs: number;
  lastScrape: string | null;
}

async function getStats(): Promise<Stats> {
  try {
    return await fetchAPI('/data/stats');
  } catch {
    return { totalListings: 0, activePortals: 0, completedJobs: 0, lastScrape: null };
  }
}

async function getPortals(): Promise<Portal[]> {
  try {
    return await fetchAPI('/portals');
  } catch {
    return [];
  }
}

export default async function DashboardPage() {
  const [stats, portals] = await Promise.all([getStats(), getPortals()]);

  const statCards = [
    { label: 'Total Listings', value: stats.totalListings.toLocaleString() },
    { label: 'Portales Activos', value: stats.activePortals },
    { label: 'Jobs Completados', value: stats.completedJobs },
    { label: 'Ultimo Scrape', value: stats.lastScrape ? new Date(stats.lastScrape).toLocaleDateString('es-MX') : 'N/A' },
  ];

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold tracking-tight">Dashboard</h1>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {statCards.map((card) => (
          <div key={card.label} className="rounded-lg border bg-card p-6">
            <p className="text-sm text-muted-foreground">{card.label}</p>
            <p className="mt-1 text-3xl font-bold">{card.value}</p>
          </div>
        ))}
      </div>

      <div className="rounded-lg border bg-card">
        <div className="border-b px-6 py-4">
          <h2 className="text-lg font-semibold">Portales</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-muted-foreground">
                <th className="px-6 py-3 font-medium">Nombre</th>
                <th className="px-6 py-3 font-medium">Estado</th>
                <th className="px-6 py-3 font-medium">Avg Listings</th>
                <th className="px-6 py-3 font-medium">Ultimo Job</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {portals.length === 0 ? (
                <tr>
                  <td colSpan={4} className="px-6 py-8 text-center text-muted-foreground">
                    No hay portales configurados
                  </td>
                </tr>
              ) : (
                portals.map((portal) => (
                  <tr key={portal.id}>
                    <td className="px-6 py-3 font-medium">{portal.name}</td>
                    <td className="px-6 py-3">
                      <StatusBadge active={portal.isActive} />
                    </td>
                    <td className="px-6 py-3">{portal.avgListings?.toLocaleString() ?? '—'}</td>
                    <td className="px-6 py-3">
                      {portal.lastJobStatus ? (
                        <JobStatusBadge status={portal.lastJobStatus} />
                      ) : (
                        <span className="text-muted-foreground">—</span>
                      )}
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

function StatusBadge({ active }: { active: boolean }) {
  return active ? (
    <span className="inline-flex items-center rounded-full bg-green-500/10 px-2 py-1 text-xs font-medium text-green-400">
      Activo
    </span>
  ) : (
    <span className="inline-flex items-center rounded-full bg-red-500/10 px-2 py-1 text-xs font-medium text-red-400">
      Inactivo
    </span>
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
