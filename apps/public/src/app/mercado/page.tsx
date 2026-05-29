import type { Metadata } from 'next';
import { getStats } from '@/lib/api';
import { formatNumber } from '@/lib/utils';
import { getOperationLabel, getPropertyTypeLabel, SITE_NAME } from '@/lib/constants';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { PriceChart } from '@/components/market/price-chart';
import { DistributionChart } from '@/components/market/distribution-chart';
import { StateGrid } from '@/components/market/state-grid';

export const revalidate = 3600;

export const metadata: Metadata = {
  title: 'Mercado Inmobiliario — Estadísticas',
  description: `Análisis del mercado inmobiliario mexicano: precios, distribución y tendencias. ${SITE_NAME}`,
};

export default async function MercadoPage() {
  const stats = await getStats();

  const priceData = stats.avgPriceByState
    .slice(0, 15)
    .map(({ state, avgPrice }) => ({
      name: state,
      value: avgPrice,
    }));

  const typeData = stats.byPropertyType
    .slice(0, 8)
    .map(({ propertyType, count }) => ({
      name: getPropertyTypeLabel(propertyType),
      value: count,
    }));

  const operationData = stats.byOperation.map(({ operation, count }) => ({
    name: getOperationLabel(operation),
    value: count,
  }));

  const stateVolumeData = stats.byState
    .slice(0, 15)
    .map(({ state, count }) => ({
      name: state,
      value: count,
    }));

  return (
    <div className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight">Mercado Inmobiliario</h1>
        <p className="mt-2 text-muted-foreground">
          Panorama general de {formatNumber(stats.totalListings)} propiedades en{' '}
          {stats.statesCovered} estados de México.
        </p>
      </div>

      {/* Charts Grid */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Price by State */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-lg">Precio promedio por estado</CardTitle>
          </CardHeader>
          <CardContent>
            <PriceChart
              data={priceData}
              format="currency"
            />
          </CardContent>
        </Card>

        {/* Volume by State */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Propiedades por estado (Top 15)</CardTitle>
          </CardHeader>
          <CardContent>
            <PriceChart
              data={stateVolumeData}
              format="number"
              color="hsl(142, 71%, 45%)"
            />
          </CardContent>
        </Card>

        {/* By Operation */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Distribución por operación</CardTitle>
          </CardHeader>
          <CardContent>
            <DistributionChart data={operationData} />
          </CardContent>
        </Card>

        {/* By Property Type */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-lg">Distribución por tipo de propiedad</CardTitle>
          </CardHeader>
          <CardContent>
            <DistributionChart data={typeData} />
          </CardContent>
        </Card>
      </div>

      {/* States Grid */}
      <div className="mt-12">
        <h2 className="mb-6 text-xl font-semibold">Detalle por estado</h2>
        <StateGrid states={stats.byState} />
      </div>
    </div>
  );
}
