'use client';

import { useRouter } from 'next/navigation';
import { useState } from 'react';
import { fetchAPI } from '@/lib/api';

export function WorkPlanActions({ id, status }: { id: string; status: string }) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);

  async function handleAction(action: 'approve' | 'cancel') {
    setLoading(true);
    try {
      await fetchAPI(`/work-plans/${id}/${action}`, { method: 'POST' });
      router.refresh();
    } catch (err) {
      console.error(`Failed to ${action} work plan:`, err);
    } finally {
      setLoading(false);
    }
  }

  if (status !== 'pending') return null;

  return (
    <div className="flex gap-2">
      <button
        onClick={() => handleAction('approve')}
        disabled={loading}
        className="rounded-md bg-green-500/10 px-3 py-1.5 text-xs font-medium text-green-400 transition-colors hover:bg-green-500/20 disabled:opacity-50"
      >
        Aprobar
      </button>
      <button
        onClick={() => handleAction('cancel')}
        disabled={loading}
        className="rounded-md bg-red-500/10 px-3 py-1.5 text-xs font-medium text-red-400 transition-colors hover:bg-red-500/20 disabled:opacity-50"
      >
        Cancelar
      </button>
    </div>
  );
}
