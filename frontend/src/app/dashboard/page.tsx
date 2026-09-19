"use client";

import { GettingStarted } from "@/components/shared/GettingStarted";
import { SystemChecklist } from "@/components/shared/SystemChecklist";
import { DauerbuchungenCard } from "./components/DauerbuchungenCard";
import { EmailEingangCard } from "./components/EmailEingangCard";
import { Inbox } from "./components/Inbox";
import { LiquiditaetCard } from "./components/LiquiditaetCard";
import { OffenePostenCard } from "./components/OffenePostenCard";

/**
 * Heute — step 4 of `docs/IA-2026-09-14.md`.
 *
 * The page now answers its own question first. The inbox at the top is every
 * decision that is actually waiting, one row each; the cards below are the
 * detail behind those rows and the place where the work happens (a Mahnung is
 * still written from the Offene-Posten card).
 *
 * Two things left in this rewrite, both on purpose:
 *
 * * the four KPI tiles (model accuracy, memory size, corrections, bookings).
 *   None of them is a decision, and IA rule 4 says say why, not how sure — a
 *   percentage on the first screen is the opposite of that. They live on Modell
 *   and Lernverlauf, where they mean something;
 * * the Schnellzugriff grid. Four links into pages the sidebar and ⌘K already
 *   reach is hunting UI, and rule 2 is that decisions come to the user.
 */
export default function HeutePage() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-xl font-bold tracking-tight text-foreground">Heute</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Was muss ich tun? — alles, was gerade auf Sie wartet
        </p>
      </div>

      <GettingStarted />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_320px]">
        <div className="space-y-8">
          <Inbox />

          <section aria-labelledby="geld-titel" id="liquiditaet" className="scroll-mt-24">
            <h2 id="geld-titel" className="mb-4 text-base font-semibold text-foreground">
              Geld und Steuern
            </h2>
            <div className="space-y-4">
              <LiquiditaetCard />
              <div id="dauerbuchungen" className="scroll-mt-24">
                <DauerbuchungenCard />
              </div>
            </div>
          </section>

          <section aria-labelledby="posten-titel" id="offene-posten" className="scroll-mt-24">
            <h2 id="posten-titel" className="mb-4 text-base font-semibold text-foreground">
              Offene Posten
            </h2>
            <OffenePostenCard />
          </section>

          <section aria-labelledby="post-titel">
            <h2 id="post-titel" className="mb-4 text-base font-semibold text-foreground">
              Posteingang
            </h2>
            <EmailEingangCard />
          </section>
        </div>

        <div className="self-start lg:sticky lg:top-[calc(var(--topbar-height)+1.5rem)]">
          <SystemChecklist />
        </div>
      </div>
    </div>
  );
}
