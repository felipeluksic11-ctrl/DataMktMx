import { Skeleton } from '@/components/ui/skeleton';

export default function MercadoLoading() {
  return (
    <div className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8">
      <Skeleton className="h-9 w-64" />
      <Skeleton className="mt-2 h-5 w-96" />
      <div className="mt-8 grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Skeleton className="h-[400px] rounded-lg lg:col-span-2" />
        <Skeleton className="h-[300px] rounded-lg" />
        <Skeleton className="h-[300px] rounded-lg" />
      </div>
    </div>
  );
}
