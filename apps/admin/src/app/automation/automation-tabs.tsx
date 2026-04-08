'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { fetchAPI } from '@/lib/api';

type Schedule = {
  id: string;
  name: string;
  mode: string;
  cronExpression: string;
  budgetMb: number;
  isEnabled: boolean;
  priority: number;
  lastRunAt: string | null;
  lastRunStatus: string | null;
  nextRunAt: string | null;
  runCount: number;
  portal: { id: string; name: string; slug: string; isActive: boolean };
  group: { id: string; name: string } | null;
};

type Health = {
  running: number;
  queued: number;
  totalSchedules: number;
  nextRun: { name: string; nextRunAt: string; portal: string } | null;
};

type Group = {
  id: string;
  name: string;
  description: string | null;
  isEnabled: boolean;
  executionMode: string;
  staggerSeconds: number;
  scheduleConfigs: { id: string; name: string; mode: string; isEnabled: boolean; portal: { name: string; slug: string } }[];
};

const tabs = ['Schedules', 'Cola & Salud', 'Historial Runs'] as const;

export function AutomationTabs({
  schedules,
  health,
  groups,
}: {
  schedules: Schedule[];
  health: Health;
  groups: Group[];
}) {
  const [activeTab, setActiveTab] = useState<(typeof tabs)[number]>('Schedules');
  const router = useRouter();

  return (
    <div>
      {/* Tab bar */}
      <div className="flex gap-1 border-b border-border mb-6">
        {tabs.map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px ${
              activeTab === tab
                ? 'border-accent-foreground text-foreground'
                : 'border-transparent text-muted-foreground hover:text-foreground'
            }`}
          >
            {tab}
          </button>
        ))}
      </div>

      {activeTab === 'Schedules' && (
        <SchedulesTab schedules={schedules} groups={groups} onRefresh={() => router.refresh()} />
      )}
      {activeTab === 'Cola & Salud' && (
        <HealthTab health={health} />
      )}
      {activeTab === 'Historial Runs' && (
        <RunsHistoryTab />
      )}
    </div>
  );
}

function SchedulesTab({
  schedules,
  groups,
  onRefresh,
}: {
  schedules: Schedule[];
  groups: Group[];
  onRefresh: () => void;
}) {
  const [loading, setLoading] = useState<string | null>(null);

  async function handleRunNow(id: string) {
    setLoading(id);
    try {
      await fetchAPI(`/schedules/${id}/run-now`, { method: 'POST' });
      onRefresh();
    } finally {
      setLoading(null);
    }
  }

  async function handleToggle(id: string) {
    await fetchAPI(`/schedules/${id}/toggle`, { method: 'PATCH' });
    onRefresh();
  }

  function statusColor(status: string | null) {
    if (!status) return 'text-muted-foreground';
    if (status === 'completed') return 'text-green-400';
    if (status === 'failed') return 'text-red-400';
    if (status === 'running') return 'text-blue-400';
    if (status === 'stopped_budget') return 'text-yellow-400';
    return 'text-muted-foreground';
  }

  function formatRelative(date: string | null) {
    if (!date) return '-';
    const d = new Date(date);
    const now = new Date();
    const diff = Math.floor((now.getTime() - d.getTime()) / 1000);
    if (diff < 60) return 'hace unos segundos';
    if (diff < 3600) return `hace ${Math.floor(diff / 60)}m`;
    if (diff < 86400) return `hace ${Math.floor(diff / 3600)}h`;
    return `hace ${Math.floor(diff / 86400)}d`;
  }

  function formatFuture(date: string | null) {
    if (!date) return '-';
    const d = new Date(date);
    const now = new Date();
    const diff = Math.floor((d.getTime() - now.getTime()) / 1000);
    if (diff < 0) return 'pendiente';
    if (diff < 60) return 'en unos segundos';
    if (diff < 3600) return `en ${Math.floor(diff / 60)}m`;
    if (diff < 86400) return `en ${Math.floor(diff / 3600)}h`;
    return `en ${Math.floor(diff / 86400)}d`;
  }

  const modeLabel: Record<string, string> = {
    incremental: 'Incremental',
    full: 'Full',
    enrich: 'Enrichment',
  };

  return (
    <div className="space-y-6">
      {/* Schedules table */}
      <div className="rounded-lg border border-border overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-card">
            <tr className="border-b border-border">
              <th className="text-left px-4 py-3 font-medium text-muted-foreground">Nombre</th>
              <th className="text-left px-4 py-3 font-medium text-muted-foreground">Portal</th>
              <th className="text-left px-4 py-3 font-medium text-muted-foreground">Modo</th>
              <th className="text-left px-4 py-3 font-medium text-muted-foreground">Cron</th>
              <th className="text-right px-4 py-3 font-medium text-muted-foreground">Budget</th>
              <th className="text-center px-4 py-3 font-medium text-muted-foreground">Activo</th>
              <th className="text-left px-4 py-3 font-medium text-muted-foreground">Prox. Run</th>
              <th className="text-left px-4 py-3 font-medium text-muted-foreground">Ult. Run</th>
              <th className="text-right px-4 py-3 font-medium text-muted-foreground">Runs</th>
              <th className="text-right px-4 py-3 font-medium text-muted-foreground">Acciones</th>
            </tr>
          </thead>
          <tbody>
            {schedules.map((s) => (
              <tr key={s.id} className="border-b border-border hover:bg-accent/50">
                <td className="px-4 py-3 font-medium text-foreground">{s.name}</td>
                <td className="px-4 py-3 text-muted-foreground">{s.portal.name}</td>
                <td className="px-4 py-3">
                  <span className="rounded-full bg-accent px-2 py-0.5 text-xs">
                    {modeLabel[s.mode] || s.mode}
                  </span>
                </td>
                <td className="px-4 py-3 font-mono text-xs text-muted-foreground">{s.cronExpression}</td>
                <td className="px-4 py-3 text-right text-muted-foreground">{s.budgetMb} MB</td>
                <td className="px-4 py-3 text-center">
                  <button
                    onClick={() => handleToggle(s.id)}
                    className={`h-5 w-9 rounded-full transition-colors ${
                      s.isEnabled ? 'bg-green-500' : 'bg-zinc-600'
                    } relative`}
                  >
                    <span
                      className={`absolute top-0.5 h-4 w-4 rounded-full bg-white transition-transform ${
                        s.isEnabled ? 'left-[18px]' : 'left-0.5'
                      }`}
                    />
                  </button>
                </td>
                <td className="px-4 py-3 text-sm text-muted-foreground">{formatFuture(s.nextRunAt)}</td>
                <td className="px-4 py-3">
                  <span className={`text-sm ${statusColor(s.lastRunStatus)}`}>
                    {s.lastRunStatus || '-'}
                  </span>
                  <span className="block text-xs text-muted-foreground">{formatRelative(s.lastRunAt)}</span>
                </td>
                <td className="px-4 py-3 text-right text-muted-foreground">{s.runCount}</td>
                <td className="px-4 py-3 text-right">
                  <button
                    onClick={() => handleRunNow(s.id)}
                    disabled={loading === s.id}
                    className="rounded bg-accent px-3 py-1 text-xs font-medium text-accent-foreground hover:bg-accent/80 disabled:opacity-50"
                  >
                    {loading === s.id ? 'Enviando...' : 'Run Now'}
                  </button>
                </td>
              </tr>
            ))}
            {schedules.length === 0 && (
              <tr>
                <td colSpan={10} className="px-4 py-8 text-center text-muted-foreground">
                  No hay schedules configurados
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Groups */}
      {groups.length > 0 && (
        <div>
          <h3 className="text-lg font-semibold text-foreground mb-3">Grupos</h3>
          <div className="space-y-3">
            {groups.map((g) => (
              <div key={g.id} className="rounded-lg border border-border p-4">
                <div className="flex items-center justify-between mb-2">
                  <div>
                    <span className="font-medium text-foreground">{g.name}</span>
                    <span className="ml-2 text-xs text-muted-foreground">
                      ({g.executionMode}, {g.staggerSeconds}s entre portales)
                    </span>
                  </div>
                  <span className={`text-xs px-2 py-0.5 rounded-full ${g.isEnabled ? 'bg-green-500/20 text-green-400' : 'bg-zinc-600/20 text-zinc-400'}`}>
                    {g.isEnabled ? 'Activo' : 'Inactivo'}
                  </span>
                </div>
                <div className="flex flex-wrap gap-2">
                  {g.scheduleConfigs.map((sc) => (
                    <span
                      key={sc.id}
                      className={`text-xs px-2 py-1 rounded border ${sc.isEnabled ? 'border-border' : 'border-border/50 opacity-50'}`}
                    >
                      {sc.portal.name} - {sc.mode}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function HealthTab({ health }: { health: Health }) {
  return (
    <div className="space-y-6">
      {/* Status cards */}
      <div className="grid grid-cols-4 gap-4">
        <div className="rounded-lg border border-border p-4">
          <p className="text-sm text-muted-foreground">Corriendo</p>
          <p className="text-3xl font-bold text-blue-400">{health.running}</p>
        </div>
        <div className="rounded-lg border border-border p-4">
          <p className="text-sm text-muted-foreground">En cola</p>
          <p className="text-3xl font-bold text-yellow-400">{health.queued}</p>
        </div>
        <div className="rounded-lg border border-border p-4">
          <p className="text-sm text-muted-foreground">Schedules activos</p>
          <p className="text-3xl font-bold text-foreground">{health.totalSchedules}</p>
        </div>
        <div className="rounded-lg border border-border p-4">
          <p className="text-sm text-muted-foreground">Proximo run</p>
          {health.nextRun ? (
            <div>
              <p className="text-lg font-semibold text-foreground">{health.nextRun.portal}</p>
              <p className="text-xs text-muted-foreground">
                {new Date(health.nextRun.nextRunAt).toLocaleString('es-MX', { timeZone: 'America/Mexico_City' })}
              </p>
            </div>
          ) : (
            <p className="text-lg text-muted-foreground">-</p>
          )}
        </div>
      </div>

      <div className="rounded-lg border border-border p-6 text-center text-muted-foreground">
        <p>La cola se actualiza automaticamente cada 30 segundos.</p>
        <p className="text-xs mt-1">Max 3 scrapers simultaneos (8 vCPU / 16 GB RAM)</p>
      </div>
    </div>
  );
}

function RunsHistoryTab() {
  const [runs, setRuns] = useState<unknown[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loaded, setLoaded] = useState(false);

  async function loadRuns(p: number) {
    const data = await fetchAPI(`/schedules/runs?page=${p}&limit=20`);
    setRuns(data.data);
    setTotal(data.total);
    setPage(p);
    setLoaded(true);
  }

  if (!loaded) {
    loadRuns(1);
    return <div className="text-muted-foreground">Cargando historial...</div>;
  }

  function statusColor(status: string) {
    if (status === 'completed') return 'text-green-400';
    if (status === 'failed') return 'text-red-400';
    if (status === 'running') return 'text-blue-400';
    if (status === 'queued') return 'text-yellow-400';
    return 'text-muted-foreground';
  }

  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-border overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-card">
            <tr className="border-b border-border">
              <th className="text-left px-4 py-3 font-medium text-muted-foreground">Schedule</th>
              <th className="text-left px-4 py-3 font-medium text-muted-foreground">Portal</th>
              <th className="text-left px-4 py-3 font-medium text-muted-foreground">Trigger</th>
              <th className="text-left px-4 py-3 font-medium text-muted-foreground">Status</th>
              <th className="text-left px-4 py-3 font-medium text-muted-foreground">Inicio</th>
              <th className="text-left px-4 py-3 font-medium text-muted-foreground">Fin</th>
              <th className="text-right px-4 py-3 font-medium text-muted-foreground">Retry</th>
              <th className="text-right px-4 py-3 font-medium text-muted-foreground">Scraped</th>
            </tr>
          </thead>
          <tbody>
            {(runs as Array<{ id: string; trigger: string; status: string; retryCount: number; startedAt: string | null; finishedAt: string | null; schedule: { name: string; portal: { name: string } }; scrapeJob: { totalScraped: number; totalNew: number } | null }>).map((r) => (
              <tr key={r.id} className="border-b border-border hover:bg-accent/50">
                <td className="px-4 py-3 text-foreground">{r.schedule?.name}</td>
                <td className="px-4 py-3 text-muted-foreground">{r.schedule?.portal?.name}</td>
                <td className="px-4 py-3">
                  <span className={`text-xs px-2 py-0.5 rounded-full ${
                    r.trigger === 'manual' ? 'bg-blue-500/20 text-blue-400' :
                    r.trigger === 'retry' ? 'bg-yellow-500/20 text-yellow-400' :
                    'bg-zinc-500/20 text-zinc-400'
                  }`}>
                    {r.trigger}
                  </span>
                </td>
                <td className={`px-4 py-3 font-medium ${statusColor(r.status)}`}>{r.status}</td>
                <td className="px-4 py-3 text-xs text-muted-foreground">
                  {r.startedAt ? new Date(r.startedAt).toLocaleString('es-MX', { timeZone: 'America/Mexico_City' }) : '-'}
                </td>
                <td className="px-4 py-3 text-xs text-muted-foreground">
                  {r.finishedAt ? new Date(r.finishedAt).toLocaleString('es-MX', { timeZone: 'America/Mexico_City' }) : '-'}
                </td>
                <td className="px-4 py-3 text-right text-muted-foreground">{r.retryCount}</td>
                <td className="px-4 py-3 text-right text-foreground">
                  {r.scrapeJob ? `${r.scrapeJob.totalNew} new / ${r.scrapeJob.totalScraped}` : '-'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {total > 20 && (
        <div className="flex justify-center gap-2">
          <button
            onClick={() => loadRuns(page - 1)}
            disabled={page <= 1}
            className="px-3 py-1 text-sm rounded border border-border disabled:opacity-30"
          >
            Anterior
          </button>
          <span className="px-3 py-1 text-sm text-muted-foreground">
            Pagina {page} de {Math.ceil(total / 20)}
          </span>
          <button
            onClick={() => loadRuns(page + 1)}
            disabled={page >= Math.ceil(total / 20)}
            className="px-3 py-1 text-sm rounded border border-border disabled:opacity-30"
          >
            Siguiente
          </button>
        </div>
      )}
    </div>
  );
}
