interface BarItem {
  label: string;
  value: number;
  color?: string;
}

interface HorizontalBarChartProps {
  data: BarItem[];
  maxValue?: number;
}

const defaultColors = [
  'bg-emerald-500', 'bg-blue-500', 'bg-violet-500', 'bg-amber-500',
  'bg-rose-500', 'bg-cyan-500', 'bg-orange-500', 'bg-pink-500',
  'bg-teal-500', 'bg-indigo-500',
];

export function HorizontalBarChart({ data, maxValue }: HorizontalBarChartProps) {
  const max = maxValue || Math.max(...data.map((d) => d.value), 1);

  return (
    <div className="space-y-3">
      {data.map((item, i) => {
        const pct = Math.max((item.value / max) * 100, 0.5);
        const color = item.color || defaultColors[i % defaultColors.length];
        return (
          <div key={item.label}>
            <div className="mb-1 flex items-center justify-between text-xs">
              <span className="truncate text-muted-foreground">{item.label}</span>
              <span className="ml-2 font-medium tabular-nums">{item.value.toLocaleString()}</span>
            </div>
            <div className="h-2 w-full rounded-full bg-secondary">
              <div
                className={`h-2 rounded-full ${color}`}
                style={{ width: `${pct}%` }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}
