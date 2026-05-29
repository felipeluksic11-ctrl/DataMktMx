import { SITE_NAME } from '@/lib/constants';

export function Footer() {
  return (
    <footer className="border-t border-border bg-background py-8">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="flex flex-col items-center justify-between gap-4 sm:flex-row">
          <p className="text-sm text-muted-foreground">
            &copy; {new Date().getFullYear()} {SITE_NAME}. Todos los derechos reservados.
          </p>
          <p className="text-xs text-muted-foreground">
            Datos agregados del mercado inmobiliario mexicano
          </p>
        </div>
      </div>
    </footer>
  );
}
