import type { Metadata } from 'next';
import { BarChart3, Shield, Database } from 'lucide-react';
import { SITE_NAME } from '@/lib/constants';
import { Card, CardContent } from '@/components/ui/card';

export const metadata: Metadata = {
  title: 'Nosotros',
  description: `${SITE_NAME} — Inteligencia de datos del mercado inmobiliario en México.`,
};

export default function NosotrosPage() {
  return (
    <div className="mx-auto max-w-4xl px-4 py-16 sm:px-6 lg:px-8">
      <h1 className="text-3xl font-bold tracking-tight">Sobre {SITE_NAME}</h1>
      <p className="mt-4 text-lg text-muted-foreground leading-relaxed">
        Somos una plataforma de inteligencia de datos enfocada en el mercado inmobiliario
        mexicano. Recopilamos, limpiamos y analizamos información de miles de propiedades
        para ofrecer una visión clara del mercado.
      </p>

      <div className="mt-12 grid grid-cols-1 gap-6 md:grid-cols-3">
        <Card>
          <CardContent className="flex flex-col items-center p-6 text-center">
            <div className="rounded-lg bg-primary/10 p-3">
              <Database className="h-6 w-6 text-primary" />
            </div>
            <h3 className="mt-4 font-semibold">Datos Agregados</h3>
            <p className="mt-2 text-sm text-muted-foreground">
              Información consolidada de múltiples fuentes del mercado inmobiliario nacional.
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="flex flex-col items-center p-6 text-center">
            <div className="rounded-lg bg-primary/10 p-3">
              <BarChart3 className="h-6 w-6 text-primary" />
            </div>
            <h3 className="mt-4 font-semibold">Análisis de Mercado</h3>
            <p className="mt-2 text-sm text-muted-foreground">
              Estadísticas detalladas por estado, municipio, tipo de propiedad y operación.
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="flex flex-col items-center p-6 text-center">
            <div className="rounded-lg bg-primary/10 p-3">
              <Shield className="h-6 w-6 text-primary" />
            </div>
            <h3 className="mt-4 font-semibold">Datos Anónimos</h3>
            <p className="mt-2 text-sm text-muted-foreground">
              Toda la información es procesada y anonimizada. No almacenamos datos personales.
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
