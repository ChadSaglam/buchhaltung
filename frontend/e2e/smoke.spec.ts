import { test, expect } from "@playwright/test";

test("login page renders", async ({ page }) => {
  await page.goto("/login");
  await expect(page.getByRole("button", { name: /login|anmelden/i })).toBeVisible();
});

test("unauthenticated user is redirected to login", async ({ page }) => {
  await page.goto("/dashboard");
  await expect(page).toHaveURL(/\/login/);
});

/**
 * Step 3 of `docs/IA-2026-09-14.md` moved the pages under the surface they
 * belong to. The old addresses are in people's bookmarks, so the redirects in
 * `next.config.ts` are part of the contract — and a redirect nobody exercises
 * is a redirect that quietly stops working.
 *
 * Asserted at the HTTP level rather than by navigating: a browser would run
 * AuthGuard and land on /login either way, which proves nothing about whether
 * the old path resolved or 404ed on the way there.
 */
const UMGEZOGEN: [string, string][] = [
  ["/dashboard/rechnungen", "/dashboard/belege"],
  ["/dashboard/rechnungen/neu", "/dashboard/belege/neu"],
  ["/dashboard/scanner", "/dashboard/belege/scanner"],
  ["/dashboard/kontoauszug", "/dashboard/bank"],
  ["/dashboard/abgleich", "/dashboard/bank/abgleich"],
  ["/dashboard/insights", "/dashboard/bank/buchungen"],
];

for (const [alt, neu] of UMGEZOGEN) {
  test(`${alt} still leads to ${neu}`, async ({ request }) => {
    const response = await request.get(alt, { maxRedirects: 0 });
    // 307, not 308: a permanent redirect is cached by the browser forever and
    // would outlive the release these are meant to cover.
    expect(response.status()).toBe(307);
    expect(response.headers()["location"]).toBe(neu);
  });
}
