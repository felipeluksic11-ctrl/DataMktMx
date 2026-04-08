import { fetchAPI } from '@/lib/api';
import { AuditTimeline } from './audit-timeline';

export default async function AuditPage() {
  const data = await fetchAPI('/audit?limit=50');

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Historial</h1>
        <p className="text-sm text-muted-foreground">
          Registro completo de todas las acciones del sistema
        </p>
      </div>

      <AuditTimeline initialEntries={data.data} initialTotal={data.total} />
    </div>
  );
}
