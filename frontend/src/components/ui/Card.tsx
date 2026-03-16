"use client";
import { motion, type HTMLMotionProps } from "motion/react";
import { forwardRef } from "react";

interface CardProps extends Omit<HTMLMotionProps<"div">, "children"> {
  hoverable?: boolean;
  children?: React.ReactNode;
}

export const Card = forwardRef<HTMLDivElement, CardProps>(
  ({ hoverable = false, className = "", children, ...props }, ref) => {
    return (
      <motion.div
        ref={ref}
        className={`
          bg-card border border-border rounded-xl
          ${hoverable ? "cursor-pointer hover:bg-muted hover:border-brand-200 transition-all duration-200" : ""}
          ${className}
        `}
        whileHover={hoverable ? { y: -2 } : undefined}
        {...props}
      >
        {children}
      </motion.div>
    );
  }
);
Card.displayName = "Card";

export function CardHeader({ className = "", children }: { className?: string; children: React.ReactNode }) {
  return (
    <div className={`px-6 pt-6 pb-0 ${className}`}>
      {children}
    </div>
  );
}

export function CardContent({ className = "", children }: { className?: string; children: React.ReactNode }) {
  return (
    <div className={`px-6 pb-6 pt-4 ${className}`}>
      {children}
    </div>
  );
}

export function CardFooter({ className = "", children }: { className?: string; children: React.ReactNode }) {
  return (
    <div className={`px-6 pb-6 pt-0 ${className}`}>
      {children}
    </div>
  );
}
