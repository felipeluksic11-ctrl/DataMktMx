'use client';

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="mx-auto flex min-h-[60vh] max-w-7xl flex-col items-center justify-center px-4">
      <h2 className="text-2xl font-bold">Algo salió mal</h2>
      <p className="mt-2 text-muted-foreground">
        No pudimos cargar los datos. Por favor intenta de nuevo.
      </p>
      <button
        onClick={reset}
        className="mt-6 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
      >
        Reintentar
      </button>
    </div>
  );
}
