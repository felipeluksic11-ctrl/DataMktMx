'use client';

import { useState } from 'react';
import { fetchAPI } from '@/lib/api';

type AuditEntry = {
  id: string;
  entityType: string;
  entityId: string | null;
  action: string;
  actor: string;
  isAutomatic: boolean;
  isSuccess: boolean;
  summary: string;
  diff: Record<string, { old: unknown; new: unknown }> | null;
  tags: string[];
  createdAt: string;
};

export function AuditTimeline({
  initialEntries,
  initialTotal,
}: {
  initialEntries: AuditEntry[];
  initialTotal: number;
}) {
  const [entries, setEntries] = useState(initialEntries);
  const [total, setTotal] = useState(initialTotal);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [filters, setFilters] = useState({ entityType: '', action: '', actor: '' });
  const [expandedId, setExpandedId] = useState<string | null>(null);

  async function loadPage(p: number) {
    const params = new URLSearchParams({ page: String(p), limit: '50' });
    if (filters.entityType) params.set('entityType', filters.entityType);
    if (filters.action) params.set('action', filters.action);
    if (filters.actor) params.set('actor', filters.actor);

    const data = await fetchAPI(`/audit?${params}`);
    setEntries(data.data);
    setTotal(data.total);
    setPage(p);
  }

  async function handleSearch() {
    if (!search.trim()) {
      loadPage(1);
      return;
    }
    const data = await fetchAPI(`/audit/search?q=${encodeURIComponent(search)}&limit=50`);
    setEntries(data.data);
    setTotal(data.total);
    setPage(1);
  }

  function actionColor(action: string, isSuccess: boolean) {
    if (!isSuccess) return 'border-red-500/30 bg-red-500/5';
    if (action === 'completed') return 'border-green-500/30 bg-green-500/5';
    if (action === 'failed') return 'border-red-500/30 bg-red-500/5';
    if (action === 'triggered' || action === 'created') return 'border-blue-500/30 bg-blue-500/5';
    if (action === 'applied') return 'border-green-500/30 bg-green-500/5';
    if (action === 'rejected') return 'border-red-500/30 bg-red-500/5';
    return 'border-border bg-card';
  }

  function actorBadge(actor: string, isAutomatic: boolean) {
    if (isAutomatic) return 'bg-blue-500/20 text-blue-400';
    if (actor === 'admin') return 'bg-purple-500/20 text-purple-400';
    return 'bg-zinc-500/20 text-zinc-400';
  }

  return (
    <div className="space-y-4">
      {/* Search + Filters */}
      <div className="flex gap-3 items-center">
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
          placeholder="Buscar en historial..."
          className="flex-1 rounded border border-border bg-card px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground"
        />
        <select
          value={filters.entityType}
          onChange={(e) => {
            setFilters((f) => ({ ...f, entityType: e.target.value }));
          }}
          className="rounded border border-border bg-card px-3 py-2 text-sm text-foreground"
        >
          <option value="">Tipo</option>
          <option value="schedule">Schedule</option>
          <option value="portal">Portal</option>
          <option value="supervisor">Supervisor</option>
          <option value="repair">Repair</option>
          <option value="scrape_job">Scrape Job</option>
        </select>
        <select
          value={filters.actor}
          onChange={(e) => {
            setFilters((f) => ({ ...f, actor: e.target.value }));
          }}
          className="rounded border border-border bg-card px-3 py-2 text-sm text-foreground"
        >
          <option value="">Actor</option>
          <option value="scheduler">Scheduler</option>
          <option value="supervisor">Supervisor</option>
          <option value="admin">Admin</option>
          <option value="system">System</option>
        </select>
        <button
          onClick={() => loadPage(1)}
          className="rounded bg-accent px-4 py-2 text-sm font-medium text-accent-foreground hover:bg-accent/80"
        >
          Filtrar
        </button>
      </div>

      {/* Timeline */}
      <div className="space-y-2">
        {entries.map((entry) => (
          <div
            key={entry.id}
            className={`rounded-lg border p-4 cursor-pointer transition-colors ${actionColor(entry.action, entry.isSuccess)}`}
            onClick={() => setExpandedId(expandedId === entry.id ? null : entry.id)}
          >
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <span className={`text-xs px-2 py-0.5 rounded-full ${actorBadge(entry.actor, entry.isAutomatic)}`}>
                    {entry.isAutomatic ? 'auto' : entry.actor}
                  </span>
                  <span className="text-xs font-medium text-muted-foreground">{entry.entityType}</span>
                  <span className="text-xs text-muted-foreground">{entry.action}</span>
                  {entry.tags?.map((tag) => (
                    <span key={tag} className="text-xs px-1.5 py-0.5 rounded bg-accent text-accent-foreground">
                      {tag}
                    </span>
                  ))}
                </div>
                <p className="text-sm text-foreground">{entry.summary}</p>
              </div>
              <span className="text-xs text-muted-foreground whitespace-nowrap ml-4">
                {new Date(entry.createdAt).toLocaleString('es-MX', { timeZone: 'America/Mexico_City' })}
              </span>
            </div>

            {/* Expanded diff */}
            {expandedId === entry.id && entry.diff && (
              <div className="mt-3 pt-3 border-t border-border">
                <p className="text-xs font-medium text-muted-foreground mb-2">Cambios:</p>
                <div className="space-y-1">
                  {Object.entries(entry.diff).map(([field, change]) => (
                    <div key={field} className="flex gap-2 text-xs font-mono">
                      <span className="text-muted-foreground w-24">{field}:</span>
                      <span className="text-red-400">{JSON.stringify(change.old)}</span>
                      <span className="text-muted-foreground">&rarr;</span>
                      <span className="text-green-400">{JSON.stringify(change.new)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ))}

        {entries.length === 0 && (
          <div className="text-center py-12 text-muted-foreground">
            No hay entradas en el historial
          </div>
        )}
      </div>

      {/* Pagination */}
      {total > 50 && (
        <div className="flex justify-center gap-2">
          <button
            onClick={() => loadPage(page - 1)}
            disabled={page <= 1}
            className="px-3 py-1 text-sm rounded border border-border disabled:opacity-30"
          >
            Anterior
          </button>
          <span className="px-3 py-1 text-sm text-muted-foreground">
            Pagina {page} de {Math.ceil(total / 50)}
          </span>
          <button
            onClick={() => loadPage(page + 1)}
            disabled={page >= Math.ceil(total / 50)}
            className="px-3 py-1 text-sm rounded border border-border disabled:opacity-30"
          >
            Siguiente
          </button>
        </div>
      )}
    </div>
  );
}
