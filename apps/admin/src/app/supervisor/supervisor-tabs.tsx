'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { fetchAPI } from '@/lib/api';

type SupervisorRun = {
  id: string;
  trigger: string;
  status: string;
  repairsSuggested: number;
  repairsApplied: number;
  repairsQueued: number;
  aiCostUsd: number;
  aiModel: string | null;
  aiTokensIn: number;
  aiTokensOut: number;
  durationS: number | null;
  createdAt: string;
  portal: { id: string; name: string; slug: string };
};

type RepairLog = {
  id: string;
  field: string;
  oldSelector: string | null;
  newSelector: string | null;
  confidence: number | null;
  reason: string | null;
  status: string;
  appliedAt: string | null;
  qualityBefore: number | null;
  qualityAfter: number | null;
  createdAt: string;
  portal: { id: string; name: string; slug: string };
};

type SupervisorConfig = {
  id: string;
  isEnabled: boolean;
  runAfterScrape: boolean;
  autoApplyThreshold: number;
  queueReviewThreshold: number;
  maxDailyCostUsd: number;
  portal: { id: string; name: string; slug: string };
};

const tabs = ['Diagnosticos', 'Reparaciones', 'Costos AI'] as const;

export function SupervisorTabs({
  runs,
  repairs,
  configs,
}: {
  runs: SupervisorRun[];
  repairs: RepairLog[];
  configs: SupervisorConfig[];
}) {
  const [activeTab, setActiveTab] = useState<(typeof tabs)[number]>('Diagnosticos');
  const router = useRouter();

  return (
    <div>
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

      {activeTab === 'Diagnosticos' && (
        <DiagnosticsTab runs={runs} configs={configs} onRefresh={() => router.refresh()} />
      )}
      {activeTab === 'Reparaciones' && (
        <RepairsTab repairs={repairs} onRefresh={() => router.refresh()} />
      )}
      {activeTab === 'Costos AI' && (
        <AICostsTab runs={runs} />
      )}
    </div>
  );
}

function DiagnosticsTab({
  runs,
  configs,
  onRefresh,
}: {
  runs: SupervisorRun[];
  configs: SupervisorConfig[];
  onRefresh: () => void;
}) {
  const [diagLoading, setDiagLoading] = useState<string | null>(null);
  const [diagSuccess, setDiagSuccess] = useState<string | null>(null);

  async function handleDiagnose(portalId: string) {
    setDiagLoading(portalId);
    setDiagSuccess(null);
    try {
      await fetchAPI(`/supervisors/diagnose/${portalId}`, { method: 'POST' });
      setDiagSuccess(portalId);
      // Wait for diagnosis to complete, then refresh
      setTimeout(() => onRefresh(), 20000);
    } catch {
      setDiagSuccess(null);
    } finally {
      setDiagLoading(null);
    }
  }

  return (
    <div className="space-y-6">
      {/* Per-portal config cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {configs.map((c) => {
          const lastRun = runs.find((r) => r.portal.id === c.portal.id);
          return (
            <div key={c.id} className="rounded-lg border border-border p-4 space-y-3">
              <div className="flex items-center justify-between">
                <span className="font-medium text-foreground">{c.portal.name}</span>
                <span className={`text-xs px-2 py-0.5 rounded-full ${c.isEnabled ? 'bg-green-500/20 text-green-400' : 'bg-zinc-600/20 text-zinc-400'}`}>
                  {c.isEnabled ? 'Activo' : 'Inactivo'}
                </span>
              </div>
              <div className="text-xs text-muted-foreground space-y-1">
                <p>Auto-apply: &ge;{(c.autoApplyThreshold * 100).toFixed(0)}% confianza</p>
                <p>Review: &ge;{(c.queueReviewThreshold * 100).toFixed(0)}% confianza</p>
                <p>Budget AI: ${c.maxDailyCostUsd}/dia</p>
                <p>Post-scrape: {c.runAfterScrape ? 'Si' : 'No'}</p>
              </div>
              {lastRun && (
                <div className="text-xs border-t border-border pt-2">
                  <p className="text-muted-foreground">
                    Ultimo: {new Date(lastRun.createdAt).toLocaleDateString('es-MX')} —{' '}
                    <span className={lastRun.status === 'completed' ? 'text-green-400' : 'text-red-400'}>
                      {lastRun.status}
                    </span>
                  </p>
                  <p className="text-muted-foreground">
                    Sugeridas: {lastRun.repairsSuggested} | Aplicadas: {lastRun.repairsApplied} | En cola: {lastRun.repairsQueued}
                  </p>
                </div>
              )}
              <button
                onClick={() => handleDiagnose(c.portal.id)}
                disabled={diagLoading === c.portal.id || diagSuccess === c.portal.id}
                className={`w-full rounded px-3 py-1.5 text-xs font-medium disabled:opacity-50 ${
                  diagSuccess === c.portal.id
                    ? 'bg-green-600 text-white'
                    : 'bg-accent text-accent-foreground hover:bg-accent/80'
                }`}
              >
                {diagLoading === c.portal.id
                  ? 'Enviando...'
                  : diagSuccess === c.portal.id
                    ? 'Diagnostico enviado — analizando (~20s)'
                    : 'Diagnosticar'}
              </button>
            </div>
          );
        })}
      </div>

      {/* Recent runs table */}
      <div>
        <h3 className="text-lg font-semibold text-foreground mb-3">Historial de Diagnosticos</h3>
        <div className="rounded-lg border border-border overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-card">
              <tr className="border-b border-border">
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Portal</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Trigger</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Status</th>
                <th className="text-right px-4 py-3 font-medium text-muted-foreground">Sugeridas</th>
                <th className="text-right px-4 py-3 font-medium text-muted-foreground">Aplicadas</th>
                <th className="text-right px-4 py-3 font-medium text-muted-foreground">En Cola</th>
                <th className="text-right px-4 py-3 font-medium text-muted-foreground">Costo AI</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Fecha</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((r) => (
                <tr key={r.id} className="border-b border-border hover:bg-accent/50">
                  <td className="px-4 py-3 text-foreground">{r.portal.name}</td>
                  <td className="px-4 py-3">
                    <span className={`text-xs px-2 py-0.5 rounded-full ${
                      r.trigger === 'manual' ? 'bg-blue-500/20 text-blue-400' :
                      r.trigger === 'auto_post_scrape' ? 'bg-green-500/20 text-green-400' :
                      'bg-zinc-500/20 text-zinc-400'
                    }`}>
                      {r.trigger}
                    </span>
                  </td>
                  <td className={`px-4 py-3 ${r.status === 'completed' ? 'text-green-400' : 'text-red-400'}`}>
                    {r.status}
                  </td>
                  <td className="px-4 py-3 text-right text-muted-foreground">{r.repairsSuggested}</td>
                  <td className="px-4 py-3 text-right text-green-400">{r.repairsApplied}</td>
                  <td className="px-4 py-3 text-right text-yellow-400">{r.repairsQueued}</td>
                  <td className="px-4 py-3 text-right text-muted-foreground">${r.aiCostUsd.toFixed(3)}</td>
                  <td className="px-4 py-3 text-xs text-muted-foreground">
                    {new Date(r.createdAt).toLocaleString('es-MX', { timeZone: 'America/Mexico_City' })}
                  </td>
                </tr>
              ))}
              {runs.length === 0 && (
                <tr>
                  <td colSpan={8} className="px-4 py-8 text-center text-muted-foreground">
                    No hay diagnosticos registrados
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function RepairsTab({ repairs, onRefresh }: { repairs: RepairLog[]; onRefresh: () => void }) {
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  async function handleAction(id: string, action: 'apply' | 'reject') {
    setActionLoading(id);
    try {
      await fetchAPI(`/supervisors/repairs/${id}/${action}`, { method: 'PATCH' });
      onRefresh();
    } finally {
      setActionLoading(null);
    }
  }

  return (
    <div className="rounded-lg border border-border overflow-hidden">
      <table className="w-full text-sm">
        <thead className="bg-card">
          <tr className="border-b border-border">
            <th className="text-left px-4 py-3 font-medium text-muted-foreground">Portal</th>
            <th className="text-left px-4 py-3 font-medium text-muted-foreground">Campo</th>
            <th className="text-left px-4 py-3 font-medium text-muted-foreground">Selector Viejo</th>
            <th className="text-left px-4 py-3 font-medium text-muted-foreground">Selector Nuevo</th>
            <th className="text-right px-4 py-3 font-medium text-muted-foreground">Confianza</th>
            <th className="text-left px-4 py-3 font-medium text-muted-foreground">Status</th>
            <th className="text-right px-4 py-3 font-medium text-muted-foreground">Q. Antes</th>
            <th className="text-right px-4 py-3 font-medium text-muted-foreground">Q. Despues</th>
            <th className="text-right px-4 py-3 font-medium text-muted-foreground">Acciones</th>
          </tr>
        </thead>
        <tbody>
          {repairs.map((r) => (
            <tr key={r.id} className="border-b border-border hover:bg-accent/50">
              <td className="px-4 py-3 text-foreground">{r.portal.name}</td>
              <td className="px-4 py-3 font-mono text-xs">{r.field}</td>
              <td className="px-4 py-3 font-mono text-xs text-red-400/70 max-w-[150px] truncate" title={r.oldSelector ?? ''}>
                {r.oldSelector || '-'}
              </td>
              <td className="px-4 py-3 font-mono text-xs text-green-400/70 max-w-[150px] truncate" title={r.newSelector ?? ''}>
                {r.newSelector || '-'}
              </td>
              <td className="px-4 py-3 text-right">
                {r.confidence !== null ? (
                  <span className={`font-medium ${r.confidence >= 0.9 ? 'text-green-400' : r.confidence >= 0.5 ? 'text-yellow-400' : 'text-red-400'}`}>
                    {(r.confidence * 100).toFixed(0)}%
                  </span>
                ) : '-'}
              </td>
              <td className="px-4 py-3">
                <span className={`text-xs px-2 py-0.5 rounded-full ${
                  r.status === 'auto_applied' ? 'bg-green-500/20 text-green-400' :
                  r.status === 'manually_applied' ? 'bg-blue-500/20 text-blue-400' :
                  r.status === 'queued' ? 'bg-yellow-500/20 text-yellow-400' :
                  r.status === 'rejected' ? 'bg-red-500/20 text-red-400' :
                  'bg-zinc-500/20 text-zinc-400'
                }`}>
                  {r.status}
                </span>
              </td>
              <td className="px-4 py-3 text-right text-muted-foreground">
                {r.qualityBefore !== null ? `${(r.qualityBefore * 100).toFixed(0)}%` : '-'}
              </td>
              <td className="px-4 py-3 text-right text-muted-foreground">
                {r.qualityAfter !== null ? `${(r.qualityAfter * 100).toFixed(0)}%` : '-'}
              </td>
              <td className="px-4 py-3 text-right">
                {r.status === 'queued' && (
                  <div className="flex gap-1 justify-end">
                    <button
                      onClick={() => handleAction(r.id, 'apply')}
                      disabled={actionLoading === r.id}
                      className="rounded bg-green-600 px-2 py-1 text-xs text-white hover:bg-green-700 disabled:opacity-50"
                    >
                      Aplicar
                    </button>
                    <button
                      onClick={() => handleAction(r.id, 'reject')}
                      disabled={actionLoading === r.id}
                      className="rounded bg-red-600 px-2 py-1 text-xs text-white hover:bg-red-700 disabled:opacity-50"
                    >
                      Rechazar
                    </button>
                  </div>
                )}
              </td>
            </tr>
          ))}
          {repairs.length === 0 && (
            <tr>
              <td colSpan={9} className="px-4 py-8 text-center text-muted-foreground">
                No hay reparaciones registradas
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

function AICostsTab({ runs }: { runs: SupervisorRun[] }) {
  const totalCost = runs.reduce((sum, r) => sum + r.aiCostUsd, 0);
  const totalTokensIn = runs.reduce((sum, r) => sum + (r.aiTokensIn ?? 0), 0);
  const totalTokensOut = runs.reduce((sum, r) => sum + (r.aiTokensOut ?? 0), 0);

  // Group by portal
  const byPortal: Record<string, { cost: number; runs: number }> = {};
  for (const r of runs) {
    const slug = r.portal.slug;
    if (!byPortal[slug]) byPortal[slug] = { cost: 0, runs: 0 };
    byPortal[slug].cost += r.aiCostUsd;
    byPortal[slug].runs += 1;
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-3 gap-4">
        <div className="rounded-lg border border-border p-4">
          <p className="text-sm text-muted-foreground">Costo total</p>
          <p className="text-3xl font-bold text-foreground">${totalCost.toFixed(3)}</p>
        </div>
        <div className="rounded-lg border border-border p-4">
          <p className="text-sm text-muted-foreground">Tokens entrada</p>
          <p className="text-3xl font-bold text-foreground">{totalTokensIn.toLocaleString()}</p>
        </div>
        <div className="rounded-lg border border-border p-4">
          <p className="text-sm text-muted-foreground">Tokens salida</p>
          <p className="text-3xl font-bold text-foreground">{totalTokensOut.toLocaleString()}</p>
        </div>
      </div>

      <div>
        <h3 className="text-lg font-semibold text-foreground mb-3">Costo por Portal</h3>
        <div className="rounded-lg border border-border overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-card">
              <tr className="border-b border-border">
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Portal</th>
                <th className="text-right px-4 py-3 font-medium text-muted-foreground">Runs</th>
                <th className="text-right px-4 py-3 font-medium text-muted-foreground">Costo</th>
                <th className="text-right px-4 py-3 font-medium text-muted-foreground">Costo/Run</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(byPortal).map(([slug, data]) => (
                <tr key={slug} className="border-b border-border">
                  <td className="px-4 py-3 text-foreground">{slug}</td>
                  <td className="px-4 py-3 text-right text-muted-foreground">{data.runs}</td>
                  <td className="px-4 py-3 text-right text-foreground">${data.cost.toFixed(3)}</td>
                  <td className="px-4 py-3 text-right text-muted-foreground">
                    ${(data.cost / data.runs).toFixed(4)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
