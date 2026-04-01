import { fetchAPI } from '@/lib/api';
import { DataFilters } from './data-filters';

interface Listing {
  id: string;
  portalSlug: string | null;
  externalId: string;
  internalCode: string | null;
  title: string | null;
  description: string | null;
  operation: string | null;
  propertyType: string | null;
  price: number | null;
  currency: string | null;
  maintenanceFee: number | null;
  streetAndNumber: string | null;
  neighborhood: string | null;
  city: string | null;
  municipality: string | null;
  state: string | null;
  country: string | null;
  zipCode: string | null;
  bedrooms: number | null;
  bathrooms: number | null;
  halfBathrooms: number | null;
  parkingSpaces: number | null;
  landM2: number | null;
  constructionM2: number | null;
  antiquity: string | null;
  constructionYears: number | null;
  conservationStatus: string | null;
  hasBalcony: boolean | null;
  hasElevator: boolean | null;
  hasStorage: boolean | null;
  builtLevels: number | null;
  imagesCount: number | null;
  urlListing: string | null;
  firstSeenAt: string | null;
  lastSeenAt: string | null;
  createdAt: string | null;
}

interface DataResponse {
  data: Listing[];
  total: number;
  page: number;
  limit: number;
}

async function getListings(searchParams: Record<string, string>): Promise<DataResponse> {
  try {
    const params = new URLSearchParams();
    for (const [key, value] of Object.entries(searchParams)) {
      if (value) params.set(key, value);
    }
    if (!params.has('limit')) params.set('limit', '30');
    if (!params.has('page')) params.set('page', '1');
    const query = params.toString();
    return await fetchAPI(`/data/listings${query ? `?${query}` : ''}`);
  } catch {
    return { data: [], total: 0, page: 1, limit: 30 };
  }
}

function formatPrice(price: number | null, currency: string | null) {
  if (price == null) return '—';
  const formatted = price.toLocaleString('es-MX');
  return currency === 'USD' ? `US$${formatted}` : `$${formatted}`;
}

function formatDate(dateStr: string | null) {
  if (!dateStr) return '—';
  return new Date(dateStr).toLocaleDateString('es-MX', { month: 'short', day: 'numeric' });
}

function num(v: number | null) {
  return v != null ? v.toLocaleString() : '—';
}

function bool(v: boolean | null) {
  if (v === true) return 'Si';
  return '—';
}

export default async function DataPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string>>;
}) {
  const params = await searchParams;
  const { data: listings, total, page, limit } = await getListings(params);
  const totalPages = Math.ceil(total / limit);

  const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:3001/api/v1';
  const exportParams = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value && key !== 'page' && key !== 'limit') exportParams.set(key, value);
  }
  const exportQuery = exportParams.toString();
  const exportUrl = `${apiBase}/data/export${exportQuery ? `?${exportQuery}` : ''}`;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold tracking-tight">Datos</h1>
        <span className="text-sm text-muted-foreground">
          {total.toLocaleString()} listings totales
        </span>
      </div>

      <DataFilters
        defaults={params}
        exportUrl={exportUrl}
        total={total}
        page={page}
        limit={limit}
        totalPages={totalPages}
      />

      <div className="rounded-lg border bg-card">
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b text-left text-muted-foreground">
                <th className="px-2 py-2 font-medium">Portal</th>
                <th className="px-2 py-2 font-medium">Titulo</th>
                <th className="px-2 py-2 font-medium">Precio</th>
                <th className="px-2 py-2 font-medium">Mant.</th>
                <th className="px-2 py-2 font-medium">Op.</th>
                <th className="px-2 py-2 font-medium">Tipo</th>
                <th className="px-2 py-2 font-medium">Direccion</th>
                <th className="px-2 py-2 font-medium">Colonia</th>
                <th className="px-2 py-2 font-medium">Municipio</th>
                <th className="px-2 py-2 font-medium">Ciudad</th>
                <th className="px-2 py-2 font-medium">Estado</th>
                <th className="px-2 py-2 font-medium">CP</th>
                <th className="px-2 py-2 font-medium text-center">Rec.</th>
                <th className="px-2 py-2 font-medium text-center">Banos</th>
                <th className="px-2 py-2 font-medium text-center">1/2B</th>
                <th className="px-2 py-2 font-medium text-center">Est.</th>
                <th className="px-2 py-2 font-medium text-right">m2 C.</th>
                <th className="px-2 py-2 font-medium text-right">m2 T.</th>
                <th className="px-2 py-2 font-medium">Antig.</th>
                <th className="px-2 py-2 font-medium text-center">Niv.</th>
                <th className="px-2 py-2 font-medium text-center">Bal.</th>
                <th className="px-2 py-2 font-medium text-center">Elev.</th>
                <th className="px-2 py-2 font-medium text-center">Bod.</th>
                <th className="px-2 py-2 font-medium text-center">Imgs</th>
                <th className="px-2 py-2 font-medium">Visto</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {listings.length === 0 ? (
                <tr>
                  <td colSpan={25} className="px-4 py-8 text-center text-muted-foreground">
                    No hay listings
                  </td>
                </tr>
              ) : (
                listings.map((l) => (
                  <tr key={l.id} className="hover:bg-muted/50">
                    <td className="px-2 py-1.5 text-muted-foreground">{l.portalSlug ?? '—'}</td>
                    <td className="max-w-[180px] truncate px-2 py-1.5 font-medium" title={l.title || ''}>
                      {l.urlListing ? (
                        <a href={l.urlListing} target="_blank" rel="noopener noreferrer" className="hover:underline text-blue-400">
                          {l.title || '—'}
                        </a>
                      ) : (l.title || '—')}
                    </td>
                    <td className="px-2 py-1.5 whitespace-nowrap">{formatPrice(l.price, l.currency)}</td>
                    <td className="px-2 py-1.5 whitespace-nowrap">{l.maintenanceFee ? `$${l.maintenanceFee.toLocaleString()}` : '—'}</td>
                    <td className="px-2 py-1.5">{l.operation ?? '—'}</td>
                    <td className="px-2 py-1.5">{l.propertyType ?? '—'}</td>
                    <td className="max-w-[120px] truncate px-2 py-1.5 text-muted-foreground" title={l.streetAndNumber || ''}>{l.streetAndNumber ?? '—'}</td>
                    <td className="max-w-[100px] truncate px-2 py-1.5 text-muted-foreground">{l.neighborhood ?? '—'}</td>
                    <td className="max-w-[100px] truncate px-2 py-1.5 text-muted-foreground">{l.municipality ?? '—'}</td>
                    <td className="px-2 py-1.5 text-muted-foreground">{l.city ?? '—'}</td>
                    <td className="px-2 py-1.5 text-muted-foreground">{l.state ?? '—'}</td>
                    <td className="px-2 py-1.5 text-muted-foreground">{l.zipCode ?? '—'}</td>
                    <td className="px-2 py-1.5 text-center">{num(l.bedrooms)}</td>
                    <td className="px-2 py-1.5 text-center">{num(l.bathrooms)}</td>
                    <td className="px-2 py-1.5 text-center">{num(l.halfBathrooms)}</td>
                    <td className="px-2 py-1.5 text-center">{num(l.parkingSpaces)}</td>
                    <td className="px-2 py-1.5 text-right">{num(l.constructionM2)}</td>
                    <td className="px-2 py-1.5 text-right">{num(l.landM2)}</td>
                    <td className="px-2 py-1.5">{l.antiquity ?? '—'}</td>
                    <td className="px-2 py-1.5 text-center">{num(l.builtLevels)}</td>
                    <td className="px-2 py-1.5 text-center">{bool(l.hasBalcony)}</td>
                    <td className="px-2 py-1.5 text-center">{bool(l.hasElevator)}</td>
                    <td className="px-2 py-1.5 text-center">{bool(l.hasStorage)}</td>
                    <td className="px-2 py-1.5 text-center">{num(l.imagesCount)}</td>
                    <td className="px-2 py-1.5 text-muted-foreground whitespace-nowrap">{formatDate(l.firstSeenAt)}</td>
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
