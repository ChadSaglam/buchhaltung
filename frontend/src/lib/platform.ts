/**
 * Platform wiring visible to the browser (chadev-platform/contracts/sso.md).
 *
 * Next.js only inlines `NEXT_PUBLIC_*` at build time, so the switcher target
 * is a separate variable from the backend's `BILLING_URL`. Empty/unset means
 * the app switcher renders no entry at all — never a dead link.
 */
const raw = process.env.NEXT_PUBLIC_BILLING_URL?.trim() ?? "";

export const BILLING_URL: string | null = raw ? raw.replace(/\/+$/, "") : null;
