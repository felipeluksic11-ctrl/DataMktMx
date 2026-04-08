import { fetchAPI } from '@/lib/api';
import { SupervisorTabs } from './supervisor-tabs';

export default async function SupervisorPage() {
  let runs: unknown[] = [];
  let repairs: unknown[] = [];
  let configs: unknown[] = [];

  try {
    const [runsData, repairsData, configsData] = await Promise.all([
      fetchAPI('/supervisors/runs?limit=20'),
      fetchAPI('/supervisors/repairs?limit=20'),
      fetchAPI('/supervisors/configs'),
    ]);
    runs = runsData.data || [];
    repairs = repairsData.data || [];
    configs = configsData || [];
  } catch { /* fallback to defaults */ }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Supervisor</h1>
        <p className="text-sm text-muted-foreground">
          Diagnosticos automaticos, reparaciones de selectores y costos AI
        </p>
      </div>

      <SupervisorTabs
        runs={runs as []}
        repairs={repairs as []}
        configs={configs as []}
      />
    </div>
  );
}
