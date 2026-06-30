import type { Metadata, Viewport } from "next";
import "./globals.css";
import { Geist, Geist_Mono } from "next/font/google";
import { Toaster } from "react-hot-toast";
import { cn } from "@/lib/utils";
import { ThemeProvider, ThemeScript } from "@/components/providers/ThemeProvider";

const geist = Geist({ subsets: ["latin"], variable: "--font-geist" });
const geistMono = Geist_Mono({ subsets: ["latin"], variable: "--font-mono" });

export const metadata: Metadata = {
  title: {
    default: "Buchhaltung — Selbstlernende Schweizer Buchhaltung",
    template: "%s · Buchhaltung",
  },
  description:
    "Selbstlernende Schweizer Buchhaltung: Belege scannen, automatisch kontieren und nach Banana exportieren.",
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f6f8fb" },
    { media: "(prefers-color-scheme: dark)", color: "#070b16" },
  ],
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="de"
      suppressHydrationWarning
      className={cn(geist.variable, geistMono.variable)}
    >
      <head>
        <ThemeScript />
      </head>
      <body className="min-h-screen bg-background text-foreground antialiased font-sans">
        <ThemeProvider>{children}</ThemeProvider>
        <Toaster
          position="bottom-right"
          toastOptions={{
            duration: 3500,
            style: {
              background: "var(--card)",
              color: "var(--foreground)",
              border: "1px solid var(--border)",
              borderRadius: "var(--radius-lg)",
              boxShadow: "var(--shadow-lg)",
              fontSize: "14px",
            },
            success: { iconTheme: { primary: "var(--success)", secondary: "var(--card)" } },
            error: { iconTheme: { primary: "var(--destructive)", secondary: "var(--card)" } },
          }}
        />
      </body>
    </html>
  );
}
