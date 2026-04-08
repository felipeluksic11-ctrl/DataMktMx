import { fetchAPI } from '@/lib/api';
import { MetricCard } from '@/components/dashboard/metric-card';
import { HorizontalBarChart } from '@/components/dashboard/horizontal-bar-chart';
import { ProgressBar } from '@/components/dashboard/progress-bar';
import { Panel } from '@/components/dashboard/panel';

interface Stats {
  totalListings: number;
  byOperation: { operation: string; count: number }[];
  byState: { state: string; count: number }[];
  byPropertyType: { propertyType: string; count: number }[];
  avgPriceByState: { state: string; avgPrice: number }[];
}

interface Quality {
  listingsToday: number;
  listingsThisWeek: number;
  fillRates: Record<string, number>;
  overallCompleteness: number;
  byPortal: {
    portalName: string;
    portalSlug: string;
    isActive: boolean;
    listingCount: number;
    priceFill: number;
    bedroomsFill: number;
    bathroomsFill: number;
    m2Fill: number;
    neighborhoodFill: number;
  }[];
}

interface Portal {
  id: string;
  name: string;
  slug: string;
  isActive: boolean;
  scrapeJobCount: number;
  latestJob: { id: string; status: string; createdAt: string } | null;
}

function formatRelative(dateStr: string | null): string {
  if (!dateStr) return 'N/A';
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'ahora';
  if (mins < 60) return `${mins}m`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h`;
  const days = Math.floor(hrs / 24);
  return `${days}d`;
}

function formatCompact(n: number): string {
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `$${(n / 1_000).toFixed(0)}K`;
  return `$${n.toLocaleString()}`;
}

const opColors: Record<string, string> = {
  venta: 'bg-emerald-500',
  renta: 'bg-blue-500',
  vacacional: 'bg-amber-500',
};

const fieldLabels: Record<string, string> = {
  price: 'Precio',
  operation: 'Operacion',
  property_type: 'Tipo',
  state: 'Estado',
  municipality: 'Municipio',
  neighborhood: 'Colonia',
  bedrooms: 'Recamaras',
  bathrooms: 'Banos',
  construction_m2: 'm2 Const.',
  land_m2: 'm2 Terreno',
  parking_spaces: 'Estac.',
};

export default async function DashboardPage() {
  let stats: Stats = { totalListings: 0, byOperation: [], byState: [], byPropertyType: [], avgPriceByState: [] };
  let quality: Quality = { listingsToday: 0, listingsThisWeek: 0, fillRates: {}, overallCompleteness: 0, byPortal: [] };
  let portals: Portal[] = [];
  let aiUsage = { totalCalls: 0, totalCostUsd: 0, todayCostUsd: 0, byPurpose: {} as Record<string, { calls: number; cost: number }> };
  let schedulerHealth = { running: 0, queued: 0, totalSchedules: 0, nextRun: null as { name: string; nextRunAt: string; portal: string } | null };
  let recentAudit: { id: string; summary: string; action: string; actor: string; isAutomatic: boolean; isSuccess: boolean; createdAt: string }[] = [];

  try {
    [stats, portals, quality, aiUsage, schedulerHealth, recentAudit] = await Promise.all([
      fetchAPI('/data/stats'),
      fetchAPI('/portals'),
      fetchAPI('/data/quality'),
      fetchAPI('/data/ai-usage').catch(() => aiUsage),
      fetchAPI('/schedules/health').catch(() => schedulerHealth),
      fetchAPI('/audit?limit=5').then((d: { data: typeof recentAudit }) => d.data).catch(() => []),
    ]);
  } catch { /* fallback to defaults */ }

  const activePortals = portals.filter((p) => p.isActive).length;
  const avgPrice = stats.avgPriceByState.length > 0
    ? stats.avgPriceByState.reduce((s, r) => s + r.avgPrice, 0) / stats.avgPriceByState.length
    : 0;

  const lastScrape = portals
    .map((p) => p.latestJob?.createdAt)
    .filter(Boolean)
    .sort()
    .reverse()[0] || null;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold tracking-tight">Dashboard</h1>

      {/* Row 1: Metric Cards */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-7">
        <MetricCard
          label="Total Listings"
          value={stats.totalListings.toLocaleString()}
          subValue={`+${quality.listingsToday.toLocaleString()} hoy`}
          color="emerald"
        />
        <MetricCard
          label="Esta Semana"
          value={quality.listingsThisWeek.toLocaleString()}
          color="blue"
        />
        <MetricCard
          label="Portales Activos"
          value={`${activePortals} / ${portals.length}`}
          color="violet"
        />
        <MetricCard
          label="Precio Promedio"
          value={formatCompact(avgPrice)}
          color="amber"
        />
        <MetricCard
          label="Data Completeness"
          value={`${quality.overallCompleteness}%`}
          color="cyan"
        />
        <MetricCard
          label="AI Supervisor"
          value={`$${aiUsage.totalCostUsd.toFixed(2)}`}
          subValue={`${aiUsage.totalCalls} calls | $${aiUsage.todayCostUsd.toFixed(2)} hoy`}
          color="rose"
        />
        <MetricCard
          label="Ultimo Scrape"
          value={formatRelative(lastScrape)}
          color="slate"
        />
      </div>

      {/* Row 1.5: System Health + Recent Activity */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Panel title="Salud del Sistema">
          <div className="grid grid-cols-3 gap-3">
            <div className="text-center">
              <p className="text-2xl font-bold text-blue-400">{schedulerHealth.running}</p>
              <p className="text-xs text-muted-foreground">Corriendo</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold text-yellow-400">{schedulerHealth.queued}</p>
              <p className="text-xs text-muted-foreground">En cola</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold text-foreground">{schedulerHealth.totalSchedules}</p>
              <p className="text-xs text-muted-foreground">Schedules</p>
            </div>
          </div>
          {schedulerHealth.nextRun && (
            <div className="mt-3 pt-3 border-t border-border text-sm text-muted-foreground">
              Proximo: <span className="text-foreground font-medium">{schedulerHealth.nextRun.portal}</span>
              {' — '}
              {new Date(schedulerHealth.nextRun.nextRunAt).toLocaleString('es-MX', { timeZone: 'America/Mexico_City', hour: '2-digit', minute: '2-digit' })}
            </div>
          )}
        </Panel>

        <Panel title="Actividad Reciente">
          {recentAudit.length > 0 ? (
            <div className="space-y-2">
              {recentAudit.map((entry) => (
                <div key={entry.id} className="flex items-start gap-2 text-sm">
                  <span className={`mt-1 h-2 w-2 rounded-full flex-shrink-0 ${
                    !entry.isSuccess ? 'bg-rose-500' :
                    entry.isAutomatic ? 'bg-blue-500' : 'bg-emerald-500'
                  }`} />
                  <div className="flex-1 min-w-0">
                    <p className="text-foreground truncate">{entry.summary}</p>
                    <p className="text-xs text-muted-foreground">
                      {entry.actor} - {formatRelative(entry.createdAt)}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">Sin actividad reciente</p>
          )}
        </Panel>
      </div>

      {/* Row 2: Operation + Property Type */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Panel title="Por Operacion">
          <HorizontalBarChart
            data={stats.byOperation.map((o) => ({
              label: o.operation.charAt(0).toUpperCase() + o.operation.slice(1),
              value: o.count,
              color: opColors[o.operation] || 'bg-slate-500',
            }))}
          />
        </Panel>
        <Panel title="Por Tipo de Propiedad">
          <HorizontalBarChart
            data={stats.byPropertyType.slice(0, 8).map((t) => ({
              label: t.propertyType,
              value: t.count,
            }))}
          />
        </Panel>
      </div>

      {/* Row 3: States + Data Quality */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Panel title="Top Estados">
          <HorizontalBarChart
            data={stats.byState.slice(0, 12).map((s) => ({
              label: s.state,
              value: s.count,
            }))}
          />
        </Panel>
        <Panel title="Calidad de Datos">
          <div className="space-y-3">
            {Object.entries(fieldLabels).map(([key, label]) => (
              <ProgressBar
                key={key}
                label={label}
                value={quality.fillRates[key] ?? 0}
              />
            ))}
          </div>
        </Panel>
      </div>

      {/* Row 4: Portal Performance Table */}
      <Panel title="Performance por Portal">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-muted-foreground">
                <th className="pb-3 font-medium">Portal</th>
                <th className="pb-3 font-medium">Status</th>
                <th className="pb-3 font-medium text-right">Listings</th>
                <th className="pb-3 font-medium text-right">Precio</th>
                <th className="pb-3 font-medium text-right">Rec.</th>
                <th className="pb-3 font-medium text-right">Banos</th>
                <th className="pb-3 font-medium text-right">m2</th>
                <th className="pb-3 font-medium text-right">Colonia</th>
                <th className="pb-3 font-medium">Ultimo Job</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {quality.byPortal.map((qp) => {
                const portal = portals.find((p) => p.slug === qp.portalSlug);
                return (
                  <tr key={qp.portalSlug} className="hover:bg-muted/50">
                    <td className="py-2.5 font-medium">{qp.portalName}</td>
                    <td className="py-2.5">
                      <span className={`inline-block rounded px-2 py-0.5 text-xs font-medium ${qp.isActive ? 'bg-emerald-500/20 text-emerald-400' : 'bg-rose-500/20 text-rose-400'}`}>
                        {qp.isActive ? 'Activo' : 'Inactivo'}
                      </span>
                    </td>
                    <td className="py-2.5 text-right tabular-nums">{qp.listingCount.toLocaleString()}</td>
                    <td className="py-2.5 text-right"><MiniBar value={qp.priceFill} /></td>
                    <td className="py-2.5 text-right"><MiniBar value={qp.bedroomsFill} /></td>
                    <td className="py-2.5 text-right"><MiniBar value={qp.bathroomsFill} /></td>
                    <td className="py-2.5 text-right"><MiniBar value={qp.m2Fill} /></td>
                    <td className="py-2.5 text-right"><MiniBar value={qp.neighborhoodFill} /></td>
                    <td className="py-2.5 text-muted-foreground">
                      {portal?.latestJob ? (
                        <span className="flex items-center gap-1.5">
                          <JobDot status={portal.latestJob.status} />
                          {formatRelative(portal.latestJob.createdAt)}
                        </span>
                      ) : '—'}
                    </td>
                  </tr>
                );
              })}
              {portals
                .filter((p) => !quality.byPortal.some((q) => q.portalSlug === p.slug))
                .map((p) => (
                  <tr key={p.slug} className="hover:bg-muted/50 text-muted-foreground">
                    <td className="py-2.5 font-medium text-foreground">{p.name}</td>
                    <td className="py-2.5">
                      <span className={`inline-block rounded px-2 py-0.5 text-xs font-medium ${p.isActive ? 'bg-emerald-500/20 text-emerald-400' : 'bg-rose-500/20 text-rose-400'}`}>
                        {p.isActive ? 'Activo' : 'Inactivo'}
                      </span>
                    </td>
                    <td className="py-2.5 text-right">0</td>
                    <td className="py-2.5 text-right">—</td>
                    <td className="py-2.5 text-right">—</td>
                    <td className="py-2.5 text-right">—</td>
                    <td className="py-2.5 text-right">—</td>
                    <td className="py-2.5 text-right">—</td>
                    <td className="py-2.5">
                      {p.latestJob ? (
                        <span className="flex items-center gap-1.5">
                          <JobDot status={p.latestJob.status} />
                          {formatRelative(p.latestJob.createdAt)}
                        </span>
                      ) : '—'}
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  );
}

function MiniBar({ value }: { value: number }) {
  const color = value >= 80 ? 'bg-emerald-500' : value >= 60 ? 'bg-amber-500' : 'bg-rose-500';
  const textColor = value >= 80 ? 'text-emerald-400' : value >= 60 ? 'text-amber-400' : 'text-rose-400';
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-12 rounded-full bg-secondary">
        <div className={`h-1.5 rounded-full ${color}`} style={{ width: `${value}%` }} />
      </div>
      <span className={`text-xs tabular-nums ${textColor}`}>{value}%</span>
    </div>
  );
}

function JobDot({ status }: { status: string }) {
  const colors: Record<string, string> = {
    completed: 'bg-emerald-500',
    running: 'bg-blue-500 animate-pulse',
    pending: 'bg-amber-500',
    failed: 'bg-rose-500',
  };
  return <span className={`inline-block h-2 w-2 rounded-full ${colors[status] || 'bg-slate-500'}`} />;
}
