import { createHmac, randomBytes } from "node:crypto";

import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

import { E2E_BILLING_URL, E2E_PLATFORM_SECRET } from "../playwright.config";

/**
 * B-36 — SSO landing page against the real backend. The token is minted here
 * exactly like billing's `create_sso_token` (HS256, contracts/sso.md) with the
 * secret playwright.config.ts hands to the API.
 */

function b64url(input: Buffer | string): string {
  return Buffer.from(input).toString("base64").replace(/=+$/, "").replace(/\+/g, "-").replace(/\//g, "_");
}

function mintSsoToken(overrides: Record<string, unknown> = {}): string {
  const now = Math.floor(Date.now() / 1000);
  const stamp = randomBytes(4).toString("hex");
  const payload = {
    iss: "billing",
    aud: "buchhaltung",
    type: "sso",
    sub: String(Number.parseInt(stamp, 16)),
    email: `sso-${stamp}@example.ch`,
    name: "Anna Muster",
    tid: Number.parseInt(stamp, 16),
    role: "admin",
    tenant: { name: `SSO AG ${stamp}`, slug: `sso-ag-${stamp}`, subscription_plan: "trial", trial_ends_at: null },
    iat: now,
    exp: now + 120,
    jti: randomBytes(16).toString("hex"),
    ...overrides,
  };
  const head = b64url(JSON.stringify({ alg: "HS256", typ: "JWT" }));
  const body = b64url(JSON.stringify(payload));
  const sig = b64url(createHmac("sha256", E2E_PLATFORM_SECRET).update(`${head}.${body}`).digest());
  return `${head}.${body}.${sig}`;
}

async function expectNoSeriousViolations(page: import("@playwright/test").Page, name: string) {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "best-practice"])
    .analyze();
  const blocking = results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
  expect(blocking.map((v) => `${v.id}: ${v.help}`).join("\n"), `${name}: serious/critical axe violations`).toBe("");
}

test("a valid hand-off token lands on the dashboard and the switcher links to Billing", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto(`/sso#token=${mintSsoToken()}`);
  await expect(page).toHaveURL(/\/dashboard$/);
  // The fragment never survives the hop.
  expect(new URL(page.url()).hash).toBe("");
  expect(await page.evaluate(() => localStorage.getItem("token"))).toBeTruthy();

  const opener = page.getByRole("button", { name: "Apps wechseln" });
  await opener.click();
  const billing = page.getByRole("menuitem", { name: /billing/i });
  await expect(billing).toBeVisible();
  await expect(billing).toHaveAttribute("href", E2E_BILLING_URL);
  await page.keyboard.press("Escape");
  await expect(billing).toBeHidden();
});

test("a used token is refused with a way back to the login page", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  const token = mintSsoToken();
  await page.goto(`/sso#token=${token}`);
  await expect(page).toHaveURL(/\/dashboard$/);
  await page.evaluate(() => localStorage.clear());

  await page.goto(`/sso#token=${token}`);
  // Next's route announcer is a second (empty) alert — scope to ours.
  const alert = page.locator("main#main").getByRole("alert");
  await expect(alert).toContainText("bereits verwendet");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expect(page.locator("main#main")).toHaveCount(1);
  await expect(page).toHaveURL(/\/sso$/);
  await expectNoSeriousViolations(page, "sso error");
  await page.getByRole("link", { name: "Zur Anmeldung" }).click();
  await expect(page).toHaveURL(/\/login/);
});

test("no token at all shows the error state", async ({ page }) => {
  await page.goto("/sso");
  await expect(page.locator("main#main").getByRole("alert")).toContainText("kein Anmelde-Token");
});
