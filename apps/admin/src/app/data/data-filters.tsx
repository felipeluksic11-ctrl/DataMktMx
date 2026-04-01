'use client';

import { useRouter } from 'next/navigation';
import { useState, useEffect } from 'react';

interface Props {
  defaults: Record<string, string>;
  exportUrl: string;
  total: number;
  page: number;
  limit: number;
  totalPages: number;
}

export function DataFilters({ defaults, exportUrl, total, page, limit, totalPages }: Props) {
  const router = useRouter();
  const [operation, setOperation] = useState(defaults.operation || '');
  const [propertyType, setPropertyType] = useState(defaults.propertyType || '');
  const [state, setState] = useState(defaults.state || '');
  const [priceMin, setPriceMin] = useState(defaults.priceMin || '');
  const [priceMax, setPriceMax] = useState(defaults.priceMax || '');

  // Auto-refresh every 30 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      router.refresh();
    }, 30000);
    return () => clearInterval(interval);
  }, [router]);

  function buildQuery(overrides: Record<string, string> = {}) {
    const params = new URLSearchParams();
    const vals = {
      operation, propertyType, state, priceMin, priceMax,
      limit: String(limit),
      page: String(page),
      ...overrides,
    };
    for (const [key, value] of Object.entries(vals)) {
      if (value && value !== '0') params.set(key, value);
    }
    return params.toString();
  }

  function handleSearch() {
    const query = buildQuery({ page: '1' });
    router.push(`/data${query ? `?${query}` : ''}`);
  }

  function goToPage(p: number) {
    const query = buildQuery({ page: String(p) });
    router.push(`/data?${query}`);
  }

  function changeLimit(newLimit: string) {
    const query = buildQuery({ limit: newLimit, page: '1' });
    router.push(`/data?${query}`);
  }

  const from = (page - 1) * limit + 1;
  const to = Math.min(page * limit, total);

  return (
    <div className="space-y-3">
      {/* Filters row */}
      <div className="flex flex-wrap items-end gap-2">
        <div className="space-y-1">
          <label className="text-xs text-muted-foreground">Operacion</label>
          <select value={operation} onChange={(e) => setOperation(e.target.value)}
            className="block w-28 rounded-md border bg-background px-2 py-1.5 text-sm">
            <option value="">Todas</option>
            <option value="venta">Venta</option>
            <option value="renta">Renta</option>
            <option value="vacacional">Vacacional</option>
          </select>
        </div>
        <div className="space-y-1">
          <label className="text-xs text-muted-foreground">Tipo</label>
          <select value={propertyType} onChange={(e) => setPropertyType(e.target.value)}
            className="block w-32 rounded-md border bg-background px-2 py-1.5 text-sm">
            <option value="">Todos</option>
            <option value="casa">Casa</option>
            <option value="departamento">Departamento</option>
            <option value="terreno">Terreno</option>
            <option value="oficina">Oficina</option>
            <option value="local_comercial">Local</option>
            <option value="bodega">Bodega</option>
            <option value="edificio">Edificio</option>
          </select>
        </div>
        <div className="space-y-1">
          <label className="text-xs text-muted-foreground">Estado</label>
          <input type="text" value={state} onChange={(e) => setState(e.target.value)}
            placeholder="Ej. Jalisco"
            className="block w-28 rounded-md border bg-background px-2 py-1.5 text-sm" />
        </div>
        <div className="space-y-1">
          <label className="text-xs text-muted-foreground">Precio Min</label>
          <input type="number" value={priceMin} onChange={(e) => setPriceMin(e.target.value)}
            placeholder="0"
            className="block w-24 rounded-md border bg-background px-2 py-1.5 text-sm" />
        </div>
        <div className="space-y-1">
          <label className="text-xs text-muted-foreground">Precio Max</label>
          <input type="number" value={priceMax} onChange={(e) => setPriceMax(e.target.value)}
            placeholder="999999999"
            className="block w-24 rounded-md border bg-background px-2 py-1.5 text-sm" />
        </div>
        <button onClick={handleSearch}
          className="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90">
          Buscar
        </button>
        <a href={exportUrl} target="_blank" rel="noopener noreferrer"
          className="rounded-md border px-3 py-1.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground">
          Exportar CSV
        </a>
      </div>

      {/* Pagination row */}
      <div className="flex items-center justify-between text-sm">
        <div className="flex items-center gap-2 text-muted-foreground">
          <span>Mostrando {from.toLocaleString()}-{to.toLocaleString()} de {total.toLocaleString()}</span>
          <select value={limit} onChange={(e) => changeLimit(e.target.value)}
            className="rounded-md border bg-background px-2 py-1 text-sm">
            <option value="30">30 / pag</option>
            <option value="100">100 / pag</option>
            <option value="500">500 / pag</option>
            <option value="1000">1000 / pag</option>
          </select>
        </div>
        <div className="flex items-center gap-1">
          <button onClick={() => goToPage(1)} disabled={page <= 1}
            className="rounded px-2 py-1 text-muted-foreground hover:bg-accent disabled:opacity-30">
            &laquo;
          </button>
          <button onClick={() => goToPage(page - 1)} disabled={page <= 1}
            className="rounded px-2 py-1 text-muted-foreground hover:bg-accent disabled:opacity-30">
            &lsaquo;
          </button>
          <span className="px-2 text-muted-foreground">
            Pag {page} de {totalPages}
          </span>
          <button onClick={() => goToPage(page + 1)} disabled={page >= totalPages}
            className="rounded px-2 py-1 text-muted-foreground hover:bg-accent disabled:opacity-30">
            &rsaquo;
          </button>
          <button onClick={() => goToPage(totalPages)} disabled={page >= totalPages}
            className="rounded px-2 py-1 text-muted-foreground hover:bg-accent disabled:opacity-30">
            &raquo;
          </button>
        </div>
      </div>
    </div>
  );
}
