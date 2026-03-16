'use client';
import { cn } from '@/lib/utils';
import { InputHTMLAttributes, forwardRef } from 'react';

const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => (
    <input
      ref={ref}
      className={cn(
        'flex h-10 w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm',
        'focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent',
        'disabled:opacity-50 dark:bg-gray-900 dark:border-gray-700 dark:text-gray-100',
        className
      )}
      {...props}
    />
  )
);
Input.displayName = 'Input';
export { Input };
