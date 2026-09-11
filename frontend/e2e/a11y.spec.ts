import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

/**
 * B-19 — automated accessibility gate. axe-core runs against the real pages
 * (same backend + registration flow as happy-path.spec.ts) and the suite
 * fails on any `serious` or `critical` violation. `moderate`/`minor`
 * findings are printed so they can be picked up without blocking.
 */

const BLOCKING = new Set(["serious", "critical"]);

async function checkA11y(page: Page, name: string) {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "best-practice"])
    .analyze();

  const blocking = results.violations.filter((v) => BLOCKING.has(v.impact ?? ""));
  const advisory = results.violations.filter((v) => !BLOCKING.has(v.impact ?? ""));
  for (const v of advisory) {
    console.warn(`[a11y:${name}] ${v.impact} ${v.id}: ${v.help} (${v.nodes.length} node(s))`);
  }
  const report = blocking
    .map((v) => `${v.impact} ${v.id}: ${v.help}\n  ${v.nodes.map((n) => `${n.target.join(" ")} — ${n.failureSummary?.split("\n")[1]?.trim() ?? ""}`).join("\n  ")}`)
    .join("\n");
  expect(report, `${name}: serious/critical axe violations`).toBe("");
}

async function register(page: Page) {
  const stamp = Date.now();
  await page.goto("/register");
  await page.getByLabel("Firmenname").fill(`A11y AG ${stamp}`);
  await page.getByLabel("Ihr Name").fill("Axe Tester");
  await page.getByLabel("E-Mail").fill(`a11y-${stamp}@example.ch`);
  await page.getByLabel("Passwort").fill("Secret123!");
  await page.getByRole("button", { name: /registrieren/i }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
}

test("login page has no serious axe violations", async ({ page }) => {
  await page.goto("/login");
  await expect(page.getByRole("button", { name: /anmelden/i })).toBeVisible();
  await checkA11y(page, "login");
});

test("skip link lands on the main landmark", async ({ page }) => {
  await register(page);
  await page.keyboard.press("Tab");
  const skip = page.getByRole("link", { name: /zum inhalt springen/i });
  await expect(skip).toBeFocused();
  await skip.press("Enter");
  await expect(page.locator("main#main")).toBeFocused();
  await expect(page.locator("html")).toHaveAttribute("lang", "de");
});

test("dialogs trap focus, close on Escape and restore focus", async ({ page }) => {
  await register(page);
  const opener = page.getByRole("button", { name: "Tastaturkürzel anzeigen" });
  await opener.focus();
  await opener.press("Enter");
  const dialog = page.getByRole("dialog", { name: "Tastaturkürzel" });
  await expect(dialog).toBeVisible();
  // Tab cycles inside the dialog.
  await page.keyboard.press("Tab");
  await page.keyboard.press("Tab");
  await expect(dialog.locator(":focus")).toHaveCount(1);
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
  await expect(opener).toBeFocused();
});

const ROUTES = ["/dashboard", "/dashboard/scanner", "/dashboard/modell", "/dashboard/settings"];

for (const theme of ["light", "dark"] as const) {
  for (const route of ROUTES) {
    test(`${route} (${theme}) has no serious axe violations`, async ({ page }) => {
      // The theme init script reads localStorage before first paint.
      await page.addInitScript((t) => localStorage.setItem("theme", t), theme);
      await register(page);
      await page.goto(route);
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      await expect(page.locator("html")).toHaveClass(theme === "dark" ? /dark/ : /^(?!.*dark).*$/);
      // Let the first data round-trip settle so the audited DOM is the real one.
      await expect(page.locator("[data-testid=page-skeleton]")).toHaveCount(0);
      await checkA11y(page, `${route} ${theme}`);
    });
  }
}
