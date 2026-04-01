import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';
import { Sidebar } from '@/components/sidebar';
import { AutoRefresh } from '@/components/auto-refresh';

const inter = Inter({ subsets: ['latin'] });

export const metadata: Metadata = {
  title: 'Propyte Admin',
  description: 'Data mining control dashboard',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="es" className="dark">
      <body className={inter.className}>
        <Sidebar />
        <AutoRefresh intervalMs={30000} />
        <main className="ml-56 min-h-screen p-8">
          {children}
        </main>
      </body>
    </html>
  );
}
