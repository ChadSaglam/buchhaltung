# Fragen an den Treuhänder — für Stufe 6 (Abschluss) und Stufe 7 (Lohn)

Stand 2026-09-17. Jede Zeile ist eine Zahl oder eine Ja/Nein-Antwort, die wir nicht
selbst herleiten können. Wo es um eine Zahl geht, steht dabei, **auf welchem Papier**
sie normalerweise steht.

---

## Stufe 7 — Lohn

Ohne diese vier Sätze rechnet das Programm bewusst gar nicht, weil eine geschätzte
Prämie wie eine richtige aussieht.

| # | Was | Wo es steht | Anmerkung |
|---|---|---|---|
| 1 | **UVG BU (%)** — Berufsunfall, Arbeitgeber | Prämienrechnung des Unfallversicherers | Betriebsspezifische Risikoklasse |
| 2 | **FAK (%)** — Familienausgleichskasse | Beitragsverfügung der Ausgleichskasse | Kantonal *und* kassenabhängig |
| 3 | **Verwaltungskostenbeitrag (%)** | Gleiche Beitragsverfügung | **Wichtig, siehe unten** |
| 4 | **UVGZ AN / AG (%)** | Police der Zusatzversicherung | Leer = nicht versichert |
| 5 | **KTG Arbeitgeber (%)** | KTG-Police | Arbeitnehmerseite ist bekannt: 0.7 % |

**Zu 3 — die Frage, die wir wirklich stellen müssen:**
Ist der Verwaltungskostenbeitrag ein Prozentsatz **der Lohnsumme** oder **der
AHV/IV/EO-Beiträge**? Die beiden unterscheiden sich um etwa den Faktor zehn. Bitte
den Satz *und* seine Grundlage notieren.

**BVG / Pensionskasse**

| # | Was | Wo es steht |
|---|---|---|
| 6 | Ist der Plan **mit oder ohne Koordinationsabzug**? | Vorsorgeausweis / Vorsorgereglement |
| 7 | Monatlicher Beitrag Arbeitnehmer und Arbeitgeber in CHF | Vorsorgeausweis |

Auf der Juni-Abrechnung sind 9.9 % des vollen Monatslohns abgezogen, ohne
Koordinationsabzug. Das ist bei einem Plan *ohne* Koordinationsabzug richtig und bei
einem BVG-Minimum-Plan falsch — aus der Abrechnung allein ist nicht erkennbar, welcher
Fall vorliegt.

**Kinderzulagen**

| # | Was |
|---|---|
| 8 | Wie viele Kinder, welcher Betrag pro Kind und Monat? |
| 9 | Bestätigung: Familienzulagen sind **nicht** AHV-pflichtig — sie gehören nicht in die Abzugsbasis |
| 10 | Gibt es einen 13. Monatslohn? Wenn ja, wie wird er ausbezahlt? |
| 11 | Quellensteuerpflicht? Wenn ja: Kanton und Tarifcode |

Frage 9 ist keine rhetorische Frage: unser Programm rechnet sie im Moment in die Basis
ein, die bisherige Abrechnung nicht. Wir korrigieren das — die Bestätigung gehört
trotzdem ins Protokoll.

---

## Stufe 6 — Abschluss (Monat · Quartal · Jahr)

### MWST

| # | Was | Warum |
|---|---|---|
| 12 | **Effektive Methode oder Saldosteuersatz?** | Bestimmt das ganze Formular |
| 13 | Bei Saldosteuersatz: welcher Satz (%)? | Die SSS-Ziffer hängt vom Satz ab |
| 14 | **Eine bereits eingereichte Quartalsabrechnung** als PDF | Zum Vergleich Ziffer für Ziffer |
| 15 | Abrechnungsperiode: quartalsweise oder halbjährlich? | |

Punkt 14 ist der eigentliche Test. Ohne ein eingereichtes Quartal zum Vergleichen
prüfen wir das Formular gegen unsere eigene Erwartung, und das prüft nichts.

### Jahresabschluss

| # | Was | Warum |
|---|---|---|
| 16 | **Eröffnungsbilanz per 1.1.** (Anfangsbestände je Konto) | Ohne sie geht die Bilanz nicht auf — das Programm bucht ab dem ersten Beleg |
| 17 | **Gewinnsteuersatz** (Kanton + Gemeinde, effektiv) | Für die Steuerrückstellung; ohne ihn zeigt die Karte nur die Bandbreite |
| 18 | Abschreibungssätze und -methode je Anlagegruppe | Wir schlagen ESTV Merkblatt A/1995 vor — stimmt das mit der bisherigen Praxis überein? |
| 19 | Wird ein **Privatanteil Fahrzeug** (6270) gebucht? Wie berechnet? | Konto ist im Plan, 2024 aber nie bebucht |
| 20 | **Verzinsung Kontokorrent 1120**: welcher Satz, auf welcher Basis? | Steht im Anhang 2024 mit CHF 1'230 |

### Anhang der Jahresrechnung

Unser Paket erstellt zurzeit **keinen Anhang** — der Abschluss 2024 enthält einen, und
für eine GmbH ist er nach OR 959c vorgeschrieben. Damit wir einen Entwurf erzeugen
können:

| # | Was |
|---|---|
| 21 | Geschäftstätigkeit — der Text von 2024, falls unverändert |
| 22 | Vollzeitstellen im Jahresdurchschnitt (Bandbreite genügt) |
| 23 | Beteiligungen und eigene Stimmanteile — weiterhin keine? |
| 24 | Wer unterschreibt, mit welcher Funktion? |

### Stundenlohn (neu seit 18.09.2026)

Das Programm kann jetzt auch Mitarbeitende im Stundenlohn abrechnen. Zwei Punkte
können wir nicht aus der Gesetzeslage ableiten, weil sie von der Kasse und vom
Vertrag abhängen:

| # | Was | Warum |
|---|---|---|
| 25 | Wie schätzt die **Pensionskasse den Jahreslohn** bei unregelmässigen Stunden? | Er entscheidet, ob jemand BVG-pflichtig ist. Wir hochrechnen zurzeit den Durchschnitt der bisher bezahlten Monate aufs Jahr — das ist eine Annahme, keine Regel |
| 26 | Wird bei Stundenlöhnern ein **13. Monatslohn** als Zuschlag pro Abrechnung vergütet, und mit welchem Prozentsatz? | Üblich sind 8.33 %, aber das steht im Arbeitsvertrag. Wir rechnen ihn bewusst **nicht** automatisch — er muss als Zulage erfasst werden, sonst erfindet das Programm eine Vereinbarung |

### MWST auf eigenen Rechnungen (neu seit 19.09.2026)

| # | Was | Warum |
|---|---|---|
| 27 | Ist die RDS Isolierungen GmbH **MWST-pflichtig / eingetragen**, und wie lautet die UID? | Die erste selbst geschriebene Rechnung weist `MWST 8.1 %` aus, im Firmenprofil steht keine MWST-Nummer. Beides zusammen geht nicht: entweder die Nummer gehört auf jede Rechnung, oder ohne Eintragung darf kein Steuersatz ausgewiesen werden. Das Programm rät hier bewusst nicht — es soll die Regel umsetzen, die für diesen Betrieb gilt |
| 28 | Falls nicht MWST-pflichtig: soll der Satz im Firmenprofil auf **0** stehen, oder das Feld ganz ausgeblendet werden? | Entscheidet, ob die Rechnungsvorlage überhaupt eine MWST-Zeile zeigt |

Bei **Ferienentschädigung** (oft 8.33 % bzw. 10.64 %) gilt dasselbe: falls sie
ausbezahlt statt bezogen wird, gehört sie heute in die Zulage. Ob das für diesen
Betrieb zutrifft, sagt der Arbeitsvertrag.

---

## Nebenbei aufgefallen, nicht dringend

Die Firmenadresse ist in den eigenen Unterlagen zweimal unterschiedlich geschrieben:
im Anhang 2024 **Bungartenstrasse 57, 8307 Effretikon**, auf der Lohnabrechnung
**Bungertenstrasse 57, 8307 Illnau-Effretikon**. Eine der beiden stimmt mit dem
Handelsregister überein; es lohnt sich, die andere zu korrigieren, bevor sie in
Rechnungen und QR-Zahlteile übernommen wird.
