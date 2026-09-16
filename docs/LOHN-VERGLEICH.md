# Lohn-Vergleich — den einen echten Monat prüfen (B-72)

Jede Lohnabrechnung, die dieses Produkt druckt, trägt **«Nicht für die
Einreichung»**. Das Wasserzeichen verschwindet nicht, wenn die Tests grün sind;
es verschwindet, wenn *ein echter Monat* gegen die Abrechnung des bisherigen
Anbieters geprüft wurde und auf den Rappen stimmt. Das ist die Bedingung aus
B-72 und sie steht bewusst so da: eine Lohnabrechnung ist die eine Zahl, die ein
Mitarbeiter nachrechnet, und ein zu wenig abgezogener AHV-Beitrag ist die
Haftung des Arbeitgebers, nicht ein Anzeigefehler.

Dieses Werkzeug macht den Vergleich mechanisch statt mühsam.

```bash
make lohn-vergleich > april.txt   # leere Vorlage
# april.txt ausfüllen: links die Eingaben, rechts was auf der alten Abrechnung steht
python3 scripts/lohn-vergleich.py april.txt
```

Das Skript braucht die Backend-Abhängigkeiten und holt sich das venv aus
`make setup` selbst — `python3 scripts/…` genügt also.

Exit-Code `0`, wenn alles stimmt, sonst `1` — der Vergleich kann also in einer
Checkliste stehen und nicht nur auf einem Bildschirm.

## Was hineingehört

Die Datei hat drei Blöcke. Zahlen dürfen so abgeschrieben werden, wie sie auf
dem Papier stehen: `6'500.00`, `6 500,00` und `6500` sind dieselbe Zahl.

### `[eingaben]` — was der Arbeitgeber weiss

Daraus rechnet **unsere** Engine. Jeder Schlüssel ist eine Zahl, die irgendwo
herkommt, und wo sie herkommt, steht dabei:

| Schlüssel | Woher |
|---|---|
| `monatslohn`, `pensum`, `eintritt`, `austritt` | Arbeitsvertrag |
| `dreizehnter`, `zulagen` | Vertrag bzw. dieser Monat |
| `brutto_ytd` | **Bruttolohn, der diesem Mitarbeiter dieses Jahr *vor* diesem Monat bezahlt wurde.** Das ist es, was die ALV-Jahresgrenze kumulativ macht — und die Zahl, die am häufigsten vergessen wird |
| `ahv_satz_an`, `alv_satz_an`, `alv_jahresgrenze` | bundesrechtlich, die Vorgaben stehen als Default drin |
| `uvg_bu_satz`, `uvg_nbu_satz`, `uvgz_satz_*` | Police der Unfallversicherung |
| `ktg_satz_*` | Police der Krankentaggeldversicherung, freiwillig — leer lassen heisst *nicht versichert* |
| `fak_satz`, `verwaltungskosten_satz` | Abrechnung der Ausgleichskasse |
| `bvg_an_monat`, `bvg_ag_monat` | **Beträge** aus der Abrechnung der Pensionskasse, nicht Sätze |
| `quellensteuer`, `quellensteuer_satz` | kantonaler Tarif für Tarifcode, Zivilstand und Kinder |

Ein Tippfehler in einem Schlüssel ist ein Fehler, kein Achselzucken: das Skript
bricht ab und nennt ihn. Ein stillschweigend ignorierter Satz ist genau der
Fehler, den dieser Vergleich finden soll.

Fehlt ein **obligatorischer** Satz, rechnet die Engine gar nicht und sagt,
welcher fehlt. Auch das ist Absicht — ein geschätzter UVG-Beitrag sieht aus wie
ein richtiger.

### `[abrechnung]` — was auf der alten Abrechnung steht

`brutto`, `ahv`, `alv`, `nbu`, `uvgz`, `ktg`, `bvg`, `quellensteuer`, `netto`.

**Eine Zeile wegzulassen heisst «ungeprüft», nicht «null».** Wenn die alte
Abrechnung eine Position wirklich nicht kennt, schreiben Sie `0.00` hin — das
ist eine Aussage, ein leeres Feld ist keine.

### `[arbeitgeber]` — dieselbe Prüfung für die Arbeitgeberseite

Optional; nicht jede alte Abrechnung zeigt sie. `ahv`, `alv`, `uvg_bu`, `uvgz`,
`ktg`, `fak`, `verwaltungskosten`, `bvg`, `total`.

## Was herauskommt

Pro Zeile: unsere Zahl, ihre Zahl, die Differenz und **woraus unsere entstanden
ist** (`6500.00 × 5.3 %`). Dahinter, für jede Abweichung, ein Befund.

Drei Dinge, die das Werkzeug ausdrücklich *nicht* tut:

1. **Es passt nichts an.** Der Zweck ist herauszufinden, ob die Engine recht
   hat. Ein Vergleich, der unsere Zahl an die fremde angleicht, hätte sich
   erledigt, bevor er gelaufen ist.
2. **Es rät nicht, ob der Satz oder die Basis anders ist.** Eine einzelne Zahl
   kann das nicht trennen: 360.40 ist 5.3 % von 6'800 *und* 5.545 % von 6'500.
   Beide Lesarten werden hingeschrieben; wenn eine der beiden eine runde Zahl
   ist, sagt der Befund, wo zuerst nachzusehen ist.
3. **Es nennt eine leere Datei nicht «stimmt».** Der Satz am Ende hebt ein
   Wasserzeichen auf. Er kommt nur, wenn Brutto und Netto genannt sind und jede
   Zeile, die wir rechnen, ein Gegenstück hat.

Ein paar Rappen Differenz werden als **Rundung** ausgewiesen und nicht als
Eingabefehler: wir runden je Zeile, andere Programme runden auf dem Total.

## Und danach

Stimmt der Monat, dann — und erst dann:

*Lohn* → **Freigabe** einschalten. Das Wasserzeichen verschwindet, und die
Abrechnungen dürfen das Haus verlassen.

Stimmt er nicht, ist jeder Befund eine Eingabe, die korrigiert gehört —
nicht eine Zeile Code. Wenn die Vorlage eine Position hat, die unsere Engine
gar nicht abbildet (ein Sanierungsbeitrag zum Beispiel), sagt das Skript das
und der Monat ist **noch nicht vergleichbar**. Das ist ein Befund für die
Roadmap, kein Grund, die Zahl zu überschreiben.
