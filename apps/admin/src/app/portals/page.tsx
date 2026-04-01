import { fetchAPI } from '@/lib/api';
import { PortalToggle } from './portal-toggle';

interface Portal {
  id: string;
  name: string;
  slug: string;
  isActive: boolean;
  avgListings: number;
  lastJobAt: string | null;
  lastJobStatus: string | null;
}

async function getPortals(): Promise<Portal[]> {
  try {
    return await fetchAPI('/portals');
  } catch {
    return [];
  }
}

export default async function PortalsPage() {
  const portals = await getPortals();

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold tracking-tight">Portales</h1>

      <div className="rounded-lg border bg-card">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-muted-foreground">
                <th className="px-6 py-3 font-medium">Nombre</th>
                <th className="px-6 py-3 font-medium">Slug</th>
                <th className="px-6 py-3 font-medium">Estado</th>
                <th className="px-6 py-3 font-medium">Avg Listings</th>
                <th className="px-6 py-3 font-medium">Ultimo Job</th>
                <th className="px-6 py-3 font-medium">Acciones</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {portals.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-6 py-8 text-center text-muted-foreground">
                    No hay portales configurados
                  </td>
                </tr>
              ) : (
                portals.map((portal) => (
                  <tr key={portal.id}>
                    <td className="px-6 py-3 font-medium">{portal.name}</td>
                    <td className="px-6 py-3 text-muted-foreground">{portal.slug}</td>
                    <td className="px-6 py-3">
                      {portal.isActive ? (
                        <span className="inline-flex items-center rounded-full bg-green-500/10 px-2 py-1 text-xs font-medium text-green-400">
                          Activo
                        </span>
                      ) : (
                        <span className="inline-flex items-center rounded-full bg-red-500/10 px-2 py-1 text-xs font-medium text-red-400">
                          Inactivo
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-3">{portal.avgListings?.toLocaleString() ?? '—'}</td>
                    <td className="px-6 py-3">
                      {portal.lastJobStatus ? (
                        <span className={`inline-flex items-center rounded-full px-2 py-1 text-xs font-medium ${
                          portal.lastJobStatus === 'completed' ? 'bg-green-500/10 text-green-400' :
                          portal.lastJobStatus === 'failed' ? 'bg-red-500/10 text-red-400' :
                          'bg-muted text-muted-foreground'
                        }`}>
                          {portal.lastJobStatus}
                        </span>
                      ) : '—'}
                    </td>
                    <td className="px-6 py-3">
                      <PortalToggle id={portal.id} isActive={portal.isActive} />
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
