import { fetchAPI } from '@/lib/api';
import { DataFilters } from './data-filters';

interface Listing {
  id: string;
  title: string;
  price: number;
  operation: string;
  propertyType: string;
  neighborhood: string | null;
  municipality: string | null;
  state: string | null;
  bedrooms: number | null;
  bathrooms: number | null;
  constructionM2: number | null;
}

interface DataResponse {
  data: Listing[];
  total: number;
}

async function getListings(searchParams: Record<string, string>): Promise<DataResponse> {
  try {
    const params = new URLSearchParams();
    for (const [key, value] of Object.entries(searchParams)) {
      if (value) params.set(key, value);
    }
    const query = params.toString();
    return await fetchAPI(`/data/listings${query ? `?${query}` : ''}`);
  } catch {
    return { data: [], total: 0 };
  }
}

export default async function DataPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string>>;
}) {
  const params = await searchParams;
  const { data: listings, total } = await getListings(params);

  const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:3001/api/v1';
  const exportParams = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value) exportParams.set(key, value);
  }
  const exportQuery = exportParams.toString();
  const exportUrl = `${apiBase}/data/export${exportQuery ? `?${exportQuery}` : ''}`;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold tracking-tight">Datos</h1>
        <span className="text-sm text-muted-foreground">{total.toLocaleString()} resultados</span>
      </div>

      <DataFilters
        defaults={params}
        exportUrl={exportUrl}
      />

      <div className="rounded-lg border bg-card">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-muted-foreground">
                <th className="px-4 py-3 font-medium">Titulo</th>
                <th className="px-4 py-3 font-medium">Precio</th>
                <th className="px-4 py-3 font-medium">Op.</th>
                <th className="px-4 py-3 font-medium">Tipo</th>
                <th className="px-4 py-3 font-medium">Colonia</th>
                <th className="px-4 py-3 font-medium">Municipio</th>
                <th className="px-4 py-3 font-medium">Estado</th>
                <th className="px-4 py-3 font-medium">Rec.</th>
                <th className="px-4 py-3 font-medium">Banos</th>
                <th className="px-4 py-3 font-medium">m2</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {listings.length === 0 ? (
                <tr>
                  <td colSpan={10} className="px-4 py-8 text-center text-muted-foreground">
                    No hay listings
                  </td>
                </tr>
              ) : (
                listings.map((l) => (
                  <tr key={l.id}>
                    <td className="max-w-[200px] truncate px-4 py-3 font-medium" title={l.title}>
                      {l.title}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap">
                      ${l.price?.toLocaleString() ?? '—'}
                    </td>
                    <td className="px-4 py-3">{l.operation}</td>
                    <td className="px-4 py-3">{l.propertyType}</td>
                    <td className="px-4 py-3 text-muted-foreground">{l.neighborhood ?? '—'}</td>
                    <td className="px-4 py-3 text-muted-foreground">{l.municipality ?? '—'}</td>
                    <td className="px-4 py-3 text-muted-foreground">{l.state ?? '—'}</td>
                    <td className="px-4 py-3">{l.bedrooms ?? '—'}</td>
                    <td className="px-4 py-3">{l.bathrooms ?? '—'}</td>
                    <td className="px-4 py-3">{l.constructionM2 ?? '—'}</td>
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
