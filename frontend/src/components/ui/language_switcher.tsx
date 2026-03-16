'use client';
import { useState, useEffect } from 'react';
import { getLocale, setLocale, getAvailableLocales, type Locale } from '@/lib/i18n';

export function LanguageSwitcher() {
  const [locale, setCurrentLocale] = useState<Locale>('de');
  useEffect(() => { setCurrentLocale(getLocale()); }, []);

  const handleChange = (newLocale: Locale) => {
    setLocale(newLocale);
    setCurrentLocale(newLocale);
    window.location.reload();
  };

  return (
    <div className="flex gap-1">
      {getAvailableLocales().map((l) => (
        <button key={l.code} onClick={() => handleChange(l.code)}
          className={`px-2.5 py-1 rounded text-xs font-medium transition-colors ${
            locale === l.code ? 'bg-brand-600 text-white' : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
          }`}>
          {l.code.toUpperCase()}
        </button>
      ))}
    </div>
  );
}
