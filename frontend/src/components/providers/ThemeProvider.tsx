"use client";

import { useEffect } from "react";
import { useThemeStore } from "@/lib/theme-store";

/**
 * Blocking script that sets the correct theme class before first paint,
 * preventing a flash of the wrong theme on initial load.
 */
const THEME_INIT_SCRIPT = `
(function () {
  try {
    var t = localStorage.getItem('theme') || 'system';
    var dark = t === 'dark' || (t === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);
    document.documentElement.classList.toggle('dark', dark);
    var accents = {
      blue:   ['#2451e6','#3b6cf6','#8eb5ff','#598dff','#3b6cf6','#2451e6','#1d3fc4'],
      violet: ['#7c3aed','#8b5cf6','#c4b5fd','#a78bfa','#8b5cf6','#7c3aed','#6d28d9'],
      emerald:['#059669','#10b981','#6ee7b7','#34d399','#10b981','#059669','#047857'],
      amber:  ['#d97706','#f59e0b','#fcd34d','#fbbf24','#f59e0b','#d97706','#b45309'],
      rose:   ['#e11d48','#f43f5e','#fda4af','#fb7185','#f43f5e','#e11d48','#be123c']
    };
    var a = accents[localStorage.getItem('accent') || 'blue'];
    if (a) {
      var s = document.documentElement.style;
      s.setProperty('--primary', a[0]); s.setProperty('--ring', a[1]);
      s.setProperty('--color-brand-300', a[2]); s.setProperty('--color-brand-400', a[3]);
      s.setProperty('--color-brand-500', a[4]); s.setProperty('--color-brand-600', a[5]);
      s.setProperty('--color-brand-700', a[6]);
    }
    // No-flash sidebar state: mark <html> so the desktop rail renders at the
    // correct width on first paint (avoids expanded → collapsed flash).
    if (localStorage.getItem('sidebar-collapsed') === 'true') {
      document.documentElement.classList.add('sidebar-collapsed');
    }
  } catch (e) {}
})();
`;

export function ThemeScript() {
  return <script dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />;
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const hydrate = useThemeStore((s) => s.hydrate);
  useEffect(() => {
    hydrate();
  }, [hydrate]);
  return <>{children}</>;
}
