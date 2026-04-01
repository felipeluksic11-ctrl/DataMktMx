'use client';

import { useRouter } from 'next/navigation';
import { useState } from 'react';

interface Props {
  defaults: Record<string, string>;
  exportUrl: string;
}

export function DataFilters({ defaults, exportUrl }: Props) {
  const router = useRouter();
  const [operation, setOperation] = useState(defaults.operation || '');
  const [propertyType, setPropertyType] = useState(defaults.propertyType || '');
  const [state, setState] = useState(defaults.state || '');
  const [priceMin, setPriceMin] = useState(defaults.priceMin || '');
  const [priceMax, setPriceMax] = useState(defaults.priceMax || '');

  function handleSearch() {
    const params = new URLSearchParams();
    if (operation) params.set('operation', operation);
    if (propertyType) params.set('propertyType', propertyType);
    if (state) params.set('state', state);
    if (priceMin) params.set('priceMin', priceMin);
    if (priceMax) params.set('priceMax', priceMax);
    const query = params.toString();
    router.push(`/data${query ? `?${query}` : ''}`);
  }

  return (
    <div className="flex flex-wrap items-end gap-3">
      <div className="space-y-1">
        <label className="text-xs text-muted-foreground">Operacion</label>
        <select
          value={operation}
          onChange={(e) => setOperation(e.target.value)}
          className="block w-32 rounded-md border bg-background px-3 py-2 text-sm"
        >
          <option value="">Todas</option>
          <option value="venta">Venta</option>
          <option value="renta">Renta</option>
          <option value="vacacional">Vacacional</option>
        </select>
      </div>
      <div className="space-y-1">
        <label className="text-xs text-muted-foreground">Tipo</label>
        <select
          value={propertyType}
          onChange={(e) => setPropertyType(e.target.value)}
          className="block w-36 rounded-md border bg-background px-3 py-2 text-sm"
        >
          <option value="">Todos</option>
          <option value="casa">Casa</option>
          <option value="departamento">Departamento</option>
          <option value="terreno">Terreno</option>
          <option value="oficina">Oficina</option>
          <option value="local">Local</option>
        </select>
      </div>
      <div className="space-y-1">
        <label className="text-xs text-muted-foreground">Estado</label>
        <input
          type="text"
          value={state}
          onChange={(e) => setState(e.target.value)}
          placeholder="Ej. Jalisco"
          className="block w-32 rounded-md border bg-background px-3 py-2 text-sm"
        />
      </div>
      <div className="space-y-1">
        <label className="text-xs text-muted-foreground">Precio Min</label>
        <input
          type="number"
          value={priceMin}
          onChange={(e) => setPriceMin(e.target.value)}
          placeholder="0"
          className="block w-28 rounded-md border bg-background px-3 py-2 text-sm"
        />
      </div>
      <div className="space-y-1">
        <label className="text-xs text-muted-foreground">Precio Max</label>
        <input
          type="number"
          value={priceMax}
          onChange={(e) => setPriceMax(e.target.value)}
          placeholder="999999999"
          className="block w-28 rounded-md border bg-background px-3 py-2 text-sm"
        />
      </div>
      <button
        onClick={handleSearch}
        className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
      >
        Buscar
      </button>
      <a
        href={exportUrl}
        target="_blank"
        rel="noopener noreferrer"
        className="rounded-md border px-4 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
      >
        Exportar CSV
      </a>
    </div>
  );
}
