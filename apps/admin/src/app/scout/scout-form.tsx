'use client';

import { useState } from 'react';
import { fetchAPI } from '@/lib/api';

interface Portal {
  id: string;
  name: string;
  slug: string;
}

interface ScoutResult {
  totalListings: number;
  pages: number;
  recommendedWorkers: number;
  estimatedHours: number;
  estimatedCost: number;
  antiBotLevel: string;
  workerAssignments: { workerId: number; pages: number; startPage: number; endPage: number }[];
}

export function ScoutForm({ portals }: { portals: Portal[] }) {
  const [portalSlug, setPortalSlug] = useState('');
  const [operation, setOperation] = useState('venta');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ScoutResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleAnalizar() {
    if (!portalSlug) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const data = await fetchAPI('/scout/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ portalSlug, operation }),
      });
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al analizar');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end gap-4">
        <div className="space-y-1.5">
          <label className="text-sm font-medium text-muted-foreground">Portal</label>
          <select
            value={portalSlug}
            onChange={(e) => setPortalSlug(e.target.value)}
            className="block w-48 rounded-md border bg-background px-3 py-2 text-sm"
          >
            <option value="">Seleccionar...</option>
            {portals.map((p) => (
              <option key={p.slug} value={p.slug}>
                {p.name}
              </option>
            ))}
          </select>
        </div>
        <div className="space-y-1.5">
          <label className="text-sm font-medium text-muted-foreground">Operacion</label>
          <select
            value={operation}
            onChange={(e) => setOperation(e.target.value)}
            className="block w-40 rounded-md border bg-background px-3 py-2 text-sm"
          >
            <option value="venta">Venta</option>
            <option value="renta">Renta</option>
            <option value="vacacional">Vacacional</option>
          </select>
        </div>
        <button
          onClick={handleAnalizar}
          disabled={loading || !portalSlug}
          className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-50"
        >
          {loading ? 'Analizando...' : 'Analizar'}
        </button>
      </div>

      {error && (
        <p className="text-sm text-red-400">{error}</p>
      )}

      {result && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
            <ResultCard label="Total Listings" value={result.totalListings.toLocaleString()} />
            <ResultCard label="Paginas" value={result.pages.toLocaleString()} />
            <ResultCard label="Workers" value={result.recommendedWorkers.toString()} />
            <ResultCard label="Horas Est." value={`${result.estimatedHours}h`} />
            <ResultCard label="Costo Est." value={`$${result.estimatedCost}`} />
            <ResultCard label="Anti-Bot" value={result.antiBotLevel} />
          </div>

          {result.workerAssignments.length > 0 && (
            <div className="rounded-lg border">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-muted-foreground">
                    <th className="px-4 py-2 font-medium">Worker</th>
                    <th className="px-4 py-2 font-medium">Paginas</th>
                    <th className="px-4 py-2 font-medium">Rango</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {result.workerAssignments.map((w) => (
                    <tr key={w.workerId}>
                      <td className="px-4 py-2">Worker {w.workerId}</td>
                      <td className="px-4 py-2">{w.pages}</td>
                      <td className="px-4 py-2">{w.startPage} - {w.endPage}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function ResultCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border bg-background p-3">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-0.5 text-lg font-bold">{value}</p>
    </div>
  );
}
