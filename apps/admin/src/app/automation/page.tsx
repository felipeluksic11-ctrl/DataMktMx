import { fetchAPI } from '@/lib/api';
import { AutomationTabs } from './automation-tabs';

export default async function AutomationPage() {
  const [schedules, health, groups] = await Promise.all([
    fetchAPI('/schedules'),
    fetchAPI('/schedules/health'),
    fetchAPI('/schedules/groups'),
  ]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Automatizacion</h1>
        <p className="text-sm text-muted-foreground">
          Programa, monitorea y controla los scrapers de forma autonoma
        </p>
      </div>

      <AutomationTabs
        schedules={schedules}
        health={health}
        groups={groups}
      />
    </div>
  );
}
