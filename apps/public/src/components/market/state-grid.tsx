import Link from 'next/link';
import { MapPin } from 'lucide-react';
import { formatNumber, slugify } from '@/lib/utils';

interface StateGridProps {
  states: { state: string; count: number }[];
}

export function StateGrid({ states }: StateGridProps) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
      {states.map(({ state, count }) => (
        <Link
          key={state}
          href={`/mercado/${slugify(state)}`}
          className="group flex flex-col rounded-lg border border-border bg-card p-4 transition-colors hover:border-primary/50 hover:bg-accent"
        >
          <div className="flex items-center gap-2">
            <MapPin className="h-4 w-4 text-muted-foreground group-hover:text-primary" />
            <span className="truncate text-sm font-medium">{state}</span>
          </div>
          <span className="mt-1 text-xs text-muted-foreground">
            {formatNumber(count)} propiedades
          </span>
        </Link>
      ))}
    </div>
  );
}
