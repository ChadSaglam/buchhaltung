import { cn } from "@/lib/utils";

/**
 * B-105: a field says whether it is required, and an error belongs to the field
 * it is about.
 *
 * Before this the Firmenprofil carried one line above a twelve-field form
 * («Noch nicht bereit. Es fehlt: IBAN.») — correct, and the user had to hunt.
 * Colour alone is not the signal (B-58, WCAG-AA): the star is text, the message
 * is text, and `aria-invalid` + `aria-describedby` carry it to a screen reader.
 */
export function SettingsField({ label, description, required, error, htmlFor, children }: {
  label: string;
  description?: string;
  /** Shows the star and, on `SettingsInput`, sets `required`. */
  required?: boolean;
  /** One sentence about *this* field. Empty means no error. */
  error?: string;
  /** id of the control, so the caption and the message really point at it. */
  htmlFor?: string;
  children: React.ReactNode;
}) {
  const errorId = error && htmlFor ? `${htmlFor}-error` : undefined;
  return (
    <div className="flex flex-col sm:flex-row sm:items-start gap-2 sm:gap-8 py-5 border-b border-border last:border-0">
      <div className="sm:w-1/3">
        <label htmlFor={htmlFor} className="text-sm font-medium text-foreground">
          {label}
          {required && (
            <span className="ml-1 text-destructive" title="Pflichtfeld">
              *<span className="sr-only"> (Pflichtfeld)</span>
            </span>
          )}
        </label>
        {description && <p className="mt-0.5 text-xs text-muted-foreground">{description}</p>}
      </div>
      <div className="sm:w-2/3">
        {children}
        {error && (
          <p id={errorId} role="alert" className="mt-1.5 text-xs font-medium text-destructive">
            {error}
          </p>
        )}
      </div>
    </div>
  );
}

export function SettingsInput({ value, onChange, type = "text", placeholder, label, id, invalid, describedBy }: {
  value: string;
  onChange: (v: string) => void;
  type?: string;
  placeholder?: string;
  /** Accessible name; the visible caption lives in the surrounding `SettingsField`. */
  label: string;
  id?: string;
  /** B-105: red border + `aria-invalid`. The message itself lives on the field. */
  invalid?: boolean;
  describedBy?: string;
}) {
  return (
    <input
      id={id}
      type={type}
      aria-label={label}
      aria-invalid={invalid || undefined}
      aria-describedby={describedBy}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      className={cn(
        "w-full rounded-lg border bg-surface px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 transition-shadow",
        invalid
          ? "border-destructive focus:ring-destructive/40"
          : "border-input focus:ring-ring"
      )}
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
