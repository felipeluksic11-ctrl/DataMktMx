import { fetchAPI } from '@/lib/api';
import { SupervisorTabs } from './supervisor-tabs';

export default async function SupervisorPage() {
  const [runsData, repairs, configs] = await Promise.all([
    fetchAPI('/supervisors/runs?limit=20'),
    fetchAPI('/supervisors/repairs?limit=20'),
    fetchAPI('/supervisors/configs'),
  ]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Supervisor</h1>
        <p className="text-sm text-muted-foreground">
          Diagnosticos automaticos, reparaciones de selectores y costos AI
        </p>
      </div>

      <SupervisorTabs
        runs={runsData.data}
        repairs={repairs.data}
        configs={configs}
      />
    </div>
  );
}
