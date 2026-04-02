interface PanelProps {
  title: string;
  children: React.ReactNode;
  className?: string;
}

export function Panel({ title, children, className = '' }: PanelProps) {
  return (
    <div className={`rounded-lg border bg-card ${className}`}>
      <div className="border-b px-5 py-3">
        <h3 className="text-sm font-medium">{title}</h3>
      </div>
      <div className="p-5">
        {children}
      </div>
    </div>
  );
}
