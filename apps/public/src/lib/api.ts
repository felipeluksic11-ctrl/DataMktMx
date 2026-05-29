const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:3001/api/v1';

async function fetchPublic<T>(path: string, revalidate: number = 3600): Promise<T> {
  const res = await fetch(`${API_BASE}/public${path}`, {
    next: { revalidate },
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export interface StatsResponse {
  totalListings: number;
  statesCovered: number;
  byOperation: { operation: string; count: number }[];
  byState: { state: string; count: number }[];
  byPropertyType: { propertyType: string; count: number }[];
  avgPriceByState: { state: string; avgPrice: number }[];
}

export interface StateStatsResponse {
  state: string;
  totalListings: number;
  byMunicipality: { municipality: string; count: number }[];
  byPropertyType: { propertyType: string; count: number }[];
  priceStats: {
    avgPrice: number;
    minPrice: number;
    maxPrice: number;
    medianPrice: number;
  } | null;
}

export interface FiltersResponse {
  states: { value: string; count: number }[];
  propertyTypes: { value: string; count: number }[];
  operations: { value: string; count: number }[];
}

export async function getStats(): Promise<StatsResponse> {
  return fetchPublic('/stats');
}

export async function getStateStats(state: string): Promise<StateStatsResponse> {
  return fetchPublic(`/stats/${encodeURIComponent(state)}`);
}

export async function getFilters(): Promise<FiltersResponse> {
  return fetchPublic('/filters', 86400);
}
