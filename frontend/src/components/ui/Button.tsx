// components/ui/Button.tsx
"use client";
import { motion, type HTMLMotionProps } from "motion/react";
import { forwardRef } from "react";

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";
type ButtonSize = "sm" | "md" | "lg";

interface ButtonProps extends Omit<HTMLMotionProps<"button">, "children"> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  icon?: React.ReactNode;
  children?: React.ReactNode;
}

const variants: Record<ButtonVariant, string> = {
  primary: "bg-brand-600 hover:bg-brand-700 text-white shadow-sm",
  secondary: "bg-white/5 hover:bg-white/10 text-foreground border border-border",
  ghost: "bg-transparent hover:bg-white/5 text-muted-foreground",
  danger: "bg-destructive/10 hover:bg-destructive/20 text-destructive border border-destructive/20",
};

const sizes: Record<ButtonSize, string> = {
  sm: "px-3 py-1.5 text-xs rounded-md",
  md: "px-4 py-2.5 text-sm rounded-lg",
  lg: "px-6 py-3 text-base rounded-lg",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = "primary", size = "md", loading, icon, children, disabled, className = "", ...props }, ref) => {
    return (
      <motion.button
        ref={ref}
        whileHover={{ scale: 1.02 }}
        whileTap={{ scale: 0.98 }}
        className={`
          inline-flex items-center justify-center gap-2 font-medium
          transition-colors duration-150 select-none
          disabled:opacity-50 disabled:pointer-events-none
          ${variants[variant]} ${sizes[size]} ${className}
        `}
        disabled={disabled || loading}
        {...props}
      >
        {loading ? (
          <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
        ) : icon}
        {children}
      </motion.button>
    );
  }
);
Button.displayName = "Button";
