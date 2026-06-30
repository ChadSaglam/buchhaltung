"use client";
import { cn } from "@/lib/utils";
import { InputHTMLAttributes, forwardRef } from "react";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  icon?: React.ReactNode;
}

const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, icon, ...props }, ref) => {
    if (icon) {
      return (
        <div className="relative">
          <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground [&_svg]:h-4 [&_svg]:w-4">
            {icon}
          </span>
          <input
            ref={ref}
            className={cn(
              "h-10 w-full rounded-lg border border-input bg-surface pl-9 pr-3 py-2 text-sm text-foreground",
              "placeholder:text-muted-foreground/70 transition-colors",
              "focus:outline-none focus:ring-2 focus:ring-ring/40 focus:border-ring",
              "disabled:opacity-50 disabled:cursor-not-allowed",
              className
            )}
            {...props}
          />
        </div>
      );
    }
    return (
      <input
        ref={ref}
        className={cn(
          "flex h-10 w-full rounded-lg border border-input bg-surface px-3 py-2 text-sm text-foreground",
          "placeholder:text-muted-foreground/70 transition-colors",
          "focus:outline-none focus:ring-2 focus:ring-ring/40 focus:border-ring",
          "disabled:opacity-50 disabled:cursor-not-allowed",
          className
        )}
        {...props}
      />
    );
  }
);
Input.displayName = "Input";
export { Input };
