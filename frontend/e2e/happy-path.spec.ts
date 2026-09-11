import { test, expect, type Page } from "@playwright/test";

/**
 * B-33 — one real user journey against the real backend (SQLite, see
 * playwright.config.ts): register → dashboard → Kontenplan → booking →
 * Insights list → CSV export.
 *
 * There is no manual "new booking" form in the UI (bookings come from the
 * Kontoauszug PDF upload or the scanner), so the booking is created through
 * the API with the token the register page stored in localStorage — exactly
 * what the Kontoauszug page does after a parse.
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? `http://127.0.0.1:${process.env.E2E_API_PORT ?? "8100"}`;

async function tokenFromStorage(page: Page): Promise<string> {
  const token = await page.evaluate(() => localStorage.getItem("token"));
  expect(token, "register must store the access token").toBeTruthy();
  return token as string;
}

test("register, browse the Kontenplan, book and export", async ({ page, request }) => {
  const stamp = Date.now();
  const email = `e2e-${stamp}@example.ch`;
  const description = `E2E Büromaterial ${stamp}`;

  // ── register via the UI ──────────────────────────────────────────────
  await page.goto("/register");
  await page.getByPlaceholder("Meine Firma GmbH").fill(`E2E AG ${stamp}`);
  await page.getByPlaceholder("Max Muster").fill("E2E Tester");
  await page.getByPlaceholder("name@firma.ch").fill(email);
  await page.getByPlaceholder("Mindestens 8 Zeichen").fill("Secret123!");
  await page.getByRole("button", { name: /registrieren/i }).click();
  await expect(page).toHaveURL(/\/dashboard$/);

  // ── Kontenplan page ──────────────────────────────────────────────────
  await page.goto("/dashboard/kontenplan");
  await expect(page.getByRole("heading", { name: "Kontenplan & Training" })).toBeVisible();

  // ── create a booking (API, with the UI's token) ───────────────────────
  const token = await tokenFromStorage(page);
  const headers = { Authorization: `Bearer ${token}` };
  const created = await request.post(`${API_URL}/api/bookings/`, {
    headers,
    data: [
      {
        datum: "15.03.2026",
        beschreibung: description,
        betrag: -108.1,
        kt_soll: "6500",
        kt_haben: "1020",
        mwst_code: "I81",
        mwst_pct: "8.10",
        mwst_amount: 8.1,
        source: "kontoauszug",
      },
    ],
  });
  expect(created.status()).toBe(200);
  expect(await created.json()).toEqual([{ id: expect.any(Number), status: "created" }]);

  // ── it shows up in the bookings list (Insights search) ───────────────
  await page.goto("/dashboard/insights");
  await page.getByPlaceholder(/Ausgaben über 500/).fill(`Büromaterial ${stamp}`);
  const row = page.getByRole("row", { name: new RegExp(description) });
  await expect(row).toBeVisible();
  await expect(row).toContainText("-108.10");
  await expect(row).toContainText("6500");

  // ── CSV export ───────────────────────────────────────────────────────
  const csv = await request.get(`${API_URL}/api/export/csv`, { headers });
  expect(csv.status()).toBe(200);
  expect(csv.headers()["content-type"]).toContain("text/csv");
  const body = await csv.text();
  expect(body.split("\n")[0]).toContain("Beschreibung");
  expect(body).toContain(description);
  expect(body).toContain("-108.1");
});
