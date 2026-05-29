import { Building2, MapPin, TrendingUp, Home } from 'lucide-react';
import { getStats } from '@/lib/api';
import { formatNumber, formatPrice } from '@/lib/utils';
import { getOperationLabel, getPropertyTypeLabel, SITE_NAME } from '@/lib/constants';
import { StatCard } from '@/components/market/stat-card';
import { StateGrid } from '@/components/market/state-grid';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

export const revalidate = 3600;

export default async function HomePage() {
  const stats = await getStats();

  const topStates = stats.byState.slice(0, 15);
  const topTypes = stats.byPropertyType.slice(0, 6);

  return (
    <div>
      {/* Hero */}
      <section className="relative overflow-hidden border-b border-border bg-gradient-to-b from-primary/5 to-background">
        <div className="mx-auto max-w-7xl px-4 py-20 sm:px-6 sm:py-28 lg:px-8">
          <div className="mx-auto max-w-3xl text-center">
            <h1 className="text-4xl font-bold tracking-tight sm:text-5xl lg:text-6xl">
              Inteligencia del mercado{' '}
              <span className="text-primary">inmobiliario</span> en México
            </h1>
            <p className="mt-6 text-lg text-muted-foreground">
              Datos agregados de {formatNumber(stats.totalListings)} propiedades
              en {stats.statesCovered} estados. Análisis de precios, tendencias y
              distribución del mercado en tiempo real.
            </p>
          </div>
        </div>
      </section>

      {/* Stats Overview */}
      <section className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard
            title="Propiedades"
            value={formatNumber(stats.totalListings)}
            subtitle="En base de datos"
            icon={Building2}
          />
          <StatCard
            title="Estados"
            value={String(stats.statesCovered)}
            subtitle="Con cobertura"
            icon={MapPin}
          />
          <StatCard
            title="Tipos de operación"
            value={String(stats.byOperation.length)}
            subtitle={stats.byOperation.map((o) => getOperationLabel(o.operation)).join(', ')}
            icon={TrendingUp}
          />
          <StatCard
            title="Tipos de propiedad"
            value={String(stats.byPropertyType.length)}
            subtitle={topTypes.slice(0, 3).map((t) => getPropertyTypeLabel(t.propertyType)).join(', ')}
            icon={Home}
          />
        </div>
      </section>

      {/* Operation Distribution */}
      <section className="mx-auto max-w-7xl px-4 pb-12 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          {/* By Operation */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Por tipo de operación</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {stats.byOperation.map(({ operation, count }) => {
                  const pct = Math.round((count / stats.totalListings) * 100);
                  return (
                    <div key={operation}>
                      <div className="flex items-center justify-between text-sm">
                        <span className="font-medium">{getOperationLabel(operation)}</span>
                        <span className="text-muted-foreground">
                          {formatNumber(count)} ({pct}%)
                        </span>
                      </div>
                      <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-muted">
                        <div
                          className="h-full rounded-full bg-primary transition-all"
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>

          {/* By Property Type */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Por tipo de propiedad</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {topTypes.map(({ propertyType, count }) => {
                  const pct = Math.round((count / stats.totalListings) * 100);
                  return (
                    <div key={propertyType}>
                      <div className="flex items-center justify-between text-sm">
                        <span className="font-medium">{getPropertyTypeLabel(propertyType)}</span>
                        <span className="text-muted-foreground">
                          {formatNumber(count)} ({pct}%)
                        </span>
                      </div>
                      <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-muted">
                        <div
                          className="h-full rounded-full bg-primary transition-all"
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        </div>
      </section>

      {/* Price by State */}
      <section className="mx-auto max-w-7xl px-4 pb-12 sm:px-6 lg:px-8">
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Precio promedio por estado</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {stats.avgPriceByState.slice(0, 15).map(({ state, avgPrice }) => (
                <Badge key={state} variant="secondary" className="px-3 py-1.5 text-xs">
                  {state}: {formatPrice(avgPrice)}
                </Badge>
              ))}
            </div>
          </CardContent>
        </Card>
      </section>

      {/* States Grid */}
      <section className="mx-auto max-w-7xl px-4 pb-16 sm:px-6 lg:px-8">
        <h2 className="mb-6 text-xl font-semibold">Explorar por estado</h2>
        <StateGrid states={topStates} />
      </section>
    </div>
  );
}
