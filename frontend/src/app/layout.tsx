import type { Metadata } from 'next';
import './globals.css';
import { Geist } from "next/font/google";
import { cn } from "@/lib/utils";

const geist = Geist({subsets:['latin'],variable:'--font-sans'});

export const metadata: Metadata = {
  title: 'RDS Buchhaltung',
  description: 'Self-learning Swiss bookkeeping SaaS',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="de" suppressHydrationWarning className={cn("font-sans", geist.variable)}>
      <body className="bg-gray-50 text-gray-900 dark:bg-gray-950 dark:text-gray-100 antialiased">
        {children}
      </body>
    </html>
  );
}
