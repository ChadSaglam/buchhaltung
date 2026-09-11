import { cn } from "@/lib/utils";

export function SettingsField({ label, description, children }: {
  label: string;
  description?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col sm:flex-row sm:items-start gap-2 sm:gap-8 py-5 border-b border-border last:border-0">
      <div className="sm:w-1/3">
        <p className="text-sm font-medium text-foreground">{label}</p>
        {description && <p className="mt-0.5 text-xs text-muted-foreground">{description}</p>}
      </div>
      <div className="sm:w-2/3">{children}</div>
    </div>
  );
}

export function SettingsInput({ value, onChange, type = "text", placeholder, label }: {
  value: string;
  onChange: (v: string) => void;
  type?: string;
  placeholder?: string;
  /** Accessible name; the visible caption lives in the surrounding `SettingsField`. */
  label: string;
}) {
  return (
    <input
      type={type}
      aria-label={label}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      className="w-full rounded-lg border border-input bg-surface px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring transition-shadow"
    />
  );
}

export function SettingsToggle({ checked, onChange, label }: {
  checked: boolean;
  onChange: (v: boolean) => void;
  label: string;
}) {
  return (
    <label className="flex items-center justify-between cursor-pointer">
      <span className="text-sm text-foreground">{label}</span>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        aria-label={label}
        onClick={() => onChange(!checked)}
        className={cn(
          "relative inline-flex h-6 w-11 items-center rounded-full transition-colors",
          checked ? "bg-brand-600" : "bg-muted"
        )}
      >
        <span className={cn(
          "inline-block h-4 w-4 rounded-full bg-white transition-transform",
          checked ? "translate-x-6" : "translate-x-1"
        )} />
      </button>
    </label>
  );
}
