interface PageHeaderProps {
  icon: string;
  title: string;
  subtitle: string;
  action?: React.ReactNode;
}

export function PageHeader({ icon, title, subtitle, action }: PageHeaderProps) {
  return (
    <div className="flex items-start justify-between mb-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
          <span>{icon}</span> {title}
        </h1>
        <p className="text-sm text-gray-500 mt-1">{subtitle}</p>
      </div>
      {action && <div>{action}</div>}
    </div>
  );
}
