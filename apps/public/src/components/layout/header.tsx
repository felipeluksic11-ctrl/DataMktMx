import Link from 'next/link';
import { BarChart3 } from 'lucide-react';
import { SITE_NAME } from '@/lib/constants';

export function Header() {
  return (
    <header className="sticky top-0 z-50 border-b border-border bg-background/80 backdrop-blur-sm">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        <Link href="/" className="flex items-center gap-2 text-lg font-bold text-primary">
          <BarChart3 className="h-6 w-6" />
          {SITE_NAME}
        </Link>
        <nav className="flex items-center gap-6 text-sm font-medium text-muted-foreground">
          <Link href="/mercado" className="transition-colors hover:text-foreground">
            Mercado
          </Link>
          <Link href="/nosotros" className="transition-colors hover:text-foreground">
            Nosotros
          </Link>
        </nav>
      </div>
    </header>
  );
}
