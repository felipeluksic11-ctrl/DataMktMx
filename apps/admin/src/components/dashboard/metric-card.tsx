interface MetricCardProps {
  label: string;
  value: string;
  subValue?: string;
  color?: string;
}

const colorMap: Record<string, string> = {
  emerald: 'border-l-emerald-500',
  blue: 'border-l-blue-500',
  violet: 'border-l-violet-500',
  amber: 'border-l-amber-500',
  cyan: 'border-l-cyan-500',
  rose: 'border-l-rose-500',
  slate: 'border-l-slate-500',
};

export function MetricCard({ label, value, subValue, color = 'emerald' }: MetricCardProps) {
  return (
    <div className={`rounded-lg border border-l-4 ${colorMap[color] || colorMap.emerald} bg-card px-4 py-3`}>
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-1 text-2xl font-bold tracking-tight">{value}</p>
      {subValue && <p className="mt-0.5 text-xs text-muted-foreground">{subValue}</p>}
    </div>
  );
}
