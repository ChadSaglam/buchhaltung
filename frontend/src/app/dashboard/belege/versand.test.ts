import { describe, expect, it } from "vitest";
import { gesendetLabel, versandBody, versandGrund, versandLabel, type VersandEntwurf } from "./versand";

function draft(overrides: Partial<VersandEntwurf> = {}): VersandEntwurf {
  return {
    document_id: 7,
    empfaenger: "kunde@beispiel.ch",
    subject: "Rechnung 2026-0001 von Muster GmbH",
    text: "Guten Tag\n\nanbei unsere Rechnung.\n",
    dateiname: "Rechnung-2026-0001.pdf",
    reply_to: "rechnung@muster.ch",
    bereit: true,
    fehlt: [],
    schon_gesendet_am: "",
    ...overrides,
  } as VersandEntwurf;
}

describe("versandLabel", () => {
  it("says send the first time and resend after that", () => {
    expect(versandLabel(draft())).toBe("Senden");
    expect(versandLabel(draft({ schon_gesendet_am: "16.09.2026 09:12" }))).toBe("Nochmals senden");
  });
});

describe("versandGrund", () => {
  it("is silent when the draft is ready", () => {
    expect(versandGrund(draft())).toBe("");
  });

  it("names what is missing rather than leaving a dead button", () => {
    const text = versandGrund(draft({ bereit: false, fehlt: ["E-Mail-Adresse des Kunden", "SMTP-Zugang"] }));
    expect(text).toContain("E-Mail-Adresse des Kunden");
    expect(text).toContain("SMTP-Zugang");
  });

  it("still says something when the server gave no reason", () => {
    expect(versandGrund(draft({ bereit: false, fehlt: [] }))).not.toBe("");
  });
});

describe("versandBody", () => {
  const base = draft();

  it("sends nothing when the owner changed nothing", () => {
    expect(versandBody(base, { empfaenger: base.empfaenger, subject: base.subject, text: base.text })).toEqual({});
  });

  it("sends only the fields that changed", () => {
    const body = versandBody(base, {
      empfaenger: "  neu@beispiel.ch  ",
      subject: base.subject,
      text: "Kurz.",
    });
    expect(body).toEqual({ empfaenger: "neu@beispiel.ch", text: "Kurz." });
  });

  it("does not treat trailing whitespace as an edit", () => {
    expect(versandBody(base, { empfaenger: `${base.empfaenger}  `, subject: `  ${base.subject}`, text: base.text })).toEqual({});
  });
});

describe("gesendetLabel", () => {
  it("dates the send, and says nothing when it never went", () => {
    expect(gesendetLabel("2026-09-16T09:12:00Z")).toBe("Gesendet 16.09.2026");
    expect(gesendetLabel(null)).toBe("");
  });
});
