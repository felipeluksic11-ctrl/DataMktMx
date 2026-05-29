import type { Metadata } from 'next';
import Link from 'next/link';
import { ArrowLeft } from 'lucide-react';
import { getStateStats, getStats } from '@/lib/api';
import { formatNumber, formatPrice, unslugify } from '@/lib/utils';
import { getPropertyTypeLabel, SITE_NAME } from '@/lib/constants';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { StatCard } from '@/components/market/stat-card';
import { PriceChart } from '@/components/market/price-chart';
import { DistributionChart } from '@/components/market/distribution-chart';
import { Building2, DollarSign, TrendingUp, MapPin } from 'lucide-react';

export const revalidate = 3600;

interface PageProps {
  params: Promise<{ state: string }>;
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { state } = await params;
  const stateName = unslugify(state);
  return {
    title: `Mercado Inmobiliario en ${stateName}`,
    description: `Estadísticas del mercado inmobiliario en ${stateName}, México. Precios, distribución y tendencias. ${SITE_NAME}`,
  };
}

export default async function StateMarketPage({ params }: PageProps) {
  const { state: stateSlug } = await params;
  const stateName = unslugify(stateSlug);

  const [stateStats, nationalStats] = await Promise.all([
    getStateStats(stateName),
    getStats(),
  ]);

  if (stateStats.totalListings === 0) {
    return (
      <div className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8">
        <Link href="/mercado" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="h-4 w-4" />
          Volver al mercado
        </Link>
        <h1 className="mt-6 text-3xl font-bold">{stateName}</h1>
        <p className="mt-4 text-muted-foreground">
          No se encontraron propiedades en este estado.
        </p>
      </div>
    );
  }

  const nationalAvg = nationalStats.avgPriceByState.reduce(
    (sum, s) => sum + s.avgPrice, 0
  ) / nationalStats.avgPriceByState.length;

  const municipalityData = stateStats.byMunicipality
    .slice(0, 15)
    .map(({ municipality, count }) => ({
      name: municipality,
      value: count,
    }));

  const typeData = stateStats.byPropertyType.map(({ propertyType, count }) => ({
    name: getPropertyTypeLabel(propertyType),
    value: count,
  }));

  const priceDiff = stateStats.priceStats
    ? ((stateStats.priceStats.avgPrice - nationalAvg) / nationalAvg) * 100
    : 0;

  return (
    <div className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8">
      <Link href="/mercado" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="h-4 w-4" />
        Volver al mercado
      </Link>

      <div className="mt-6 mb-8">
        <h1 className="text-3xl font-bold tracking-tight">{stateStats.state || stateName}</h1>
        <p className="mt-2 text-muted-foreground">
          Análisis del mercado inmobiliario en {stateStats.state || stateName}
        </p>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Propiedades"
          value={formatNumber(stateStats.totalListings)}
          subtitle={`${((stateStats.totalListings / nationalStats.totalListings) * 100).toFixed(1)}% del total nacional`}
          icon={Building2}
        />
        {stateStats.priceStats && (
          <>
            <StatCard
              title="Precio promedio"
              value={formatPrice(stateStats.priceStats.avgPrice)}
              subtitle={`${priceDiff > 0 ? '+' : ''}${priceDiff.toFixed(0)}% vs promedio nacional`}
              icon={DollarSign}
            />
            <StatCard
              title="Precio mediano"
              value={formatPrice(stateStats.priceStats.medianPrice)}
              icon={TrendingUp}
            />
            <StatCard
              title="Municipios"
              value={String(stateStats.byMunicipality.length)}
              subtitle="Con propiedades"
              icon={MapPin}
            />
          </>
        )}
      </div>

      {/* Charts */}
      <div className="mt-8 grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* By Municipality */}
        {municipalityData.length > 0 && (
          <Card className="lg:col-span-2">
            <CardHeader>
              <CardTitle className="text-lg">Propiedades por municipio</CardTitle>
            </CardHeader>
            <CardContent>
              <PriceChart
                data={municipalityData}
                format="number"
                color="hsl(142, 71%, 45%)"
              />
            </CardContent>
          </Card>
        )}

        {/* By Property Type */}
        {typeData.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Por tipo de propiedad</CardTitle>
            </CardHeader>
            <CardContent>
              <DistributionChart data={typeData} />
            </CardContent>
          </Card>
        )}

        {/* Price Range */}
        {stateStats.priceStats && (
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Rango de precios</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">Mínimo</span>
                  <span className="font-medium">{formatPrice(stateStats.priceStats.minPrice)}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">Mediano</span>
                  <span className="font-medium">{formatPrice(stateStats.priceStats.medianPrice)}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">Promedio</span>
                  <span className="font-medium">{formatPrice(stateStats.priceStats.avgPrice)}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">Máximo</span>
                  <span className="font-medium">{formatPrice(stateStats.priceStats.maxPrice)}</span>
                </div>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
