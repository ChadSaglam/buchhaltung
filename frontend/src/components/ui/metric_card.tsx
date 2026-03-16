interface MetricCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon?: React.ReactNode;
  accent?: 'blue' | 'green' | 'amber' | 'red' | 'gray';
}

const accents = {
  blue: 'border-l-brand-500',
  green: 'border-l-green-500',
  amber: 'border-l-amber-500',
  red: 'border-l-red-500',
  gray: 'border-l-gray-300',
};

export function MetricCard({ title, value, subtitle, icon, accent = 'blue' }: MetricCardProps) {
  return (
    <div className={`bg-white rounded-xl border border-gray-200 border-l-4 ${accents[accent]} p-4 shadow-sm`}>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">{title}</p>
          <p className="text-2xl font-bold text-gray-900 mt-1">{value}</p>
          {subtitle && <p className="text-xs text-gray-400 mt-0.5">{subtitle}</p>}
        </div>
        {icon && <div className="text-2xl">{icon}</div>}
      </div>
    </div>
  );
}
