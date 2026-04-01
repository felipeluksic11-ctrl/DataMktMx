import { fetchAPI } from '@/lib/api';
import { ScoutForm } from './scout-form';
import { WorkPlanActions } from './work-plan-actions';

interface Portal {
  id: string;
  name: string;
  slug: string;
}

interface WorkPlan {
  id: string;
  portalName: string;
  operation: string;
  status: string;
  totalListings: number;
  workers: number;
  estimatedHours: number;
}

async function getPortals(): Promise<Portal[]> {
  try {
    return await fetchAPI('/portals');
  } catch {
    return [];
  }
}

async function getWorkPlans(): Promise<WorkPlan[]> {
  try {
    return await fetchAPI('/work-plans');
  } catch {
    return [];
  }
}

export default async function ScoutPage() {
  const [portals, workPlans] = await Promise.all([getPortals(), getWorkPlans()]);

  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-bold tracking-tight">Scout & Work Plans</h1>

      <div className="rounded-lg border bg-card p-6">
        <h2 className="mb-4 text-lg font-semibold">Nuevo Scout</h2>
        <ScoutForm portals={portals} />
      </div>

      <div className="rounded-lg border bg-card">
        <div className="border-b px-6 py-4">
          <h2 className="text-lg font-semibold">Work Plans</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-muted-foreground">
                <th className="px-6 py-3 font-medium">Portal</th>
                <th className="px-6 py-3 font-medium">Operacion</th>
                <th className="px-6 py-3 font-medium">Estado</th>
                <th className="px-6 py-3 font-medium">Listings</th>
                <th className="px-6 py-3 font-medium">Workers</th>
                <th className="px-6 py-3 font-medium">Horas Est.</th>
                <th className="px-6 py-3 font-medium">Acciones</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {workPlans.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-6 py-8 text-center text-muted-foreground">
                    No hay work plans
                  </td>
                </tr>
              ) : (
                workPlans.map((plan) => (
                  <tr key={plan.id}>
                    <td className="px-6 py-3 font-medium">{plan.portalName}</td>
                    <td className="px-6 py-3">{plan.operation}</td>
                    <td className="px-6 py-3">
                      <PlanStatusBadge status={plan.status} />
                    </td>
                    <td className="px-6 py-3">{plan.totalListings.toLocaleString()}</td>
                    <td className="px-6 py-3">{plan.workers}</td>
                    <td className="px-6 py-3">{plan.estimatedHours}h</td>
                    <td className="px-6 py-3">
                      <WorkPlanActions id={plan.id} status={plan.status} />
                    </td>
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

function PlanStatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    pending: 'bg-yellow-500/10 text-yellow-400',
    approved: 'bg-green-500/10 text-green-400',
    running: 'bg-blue-500/10 text-blue-400',
    completed: 'bg-green-500/10 text-green-400',
    cancelled: 'bg-red-500/10 text-red-400',
  };
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-1 text-xs font-medium ${styles[status] ?? 'bg-muted text-muted-foreground'}`}>
      {status}
    </span>
  );
}
