import type { Schemas } from "@/lib/api-schema";

export type EmailEingang = Schemas["EmailEingangResponse"];
export type MailSettings = Schemas["MailSettingsOut"];
export type EmailMessageOut = Schemas["EmailMessageOut"];

export const STATUS_LABEL: Record<string, string> = {
  verarbeitet: "Übernommen",
  abgelehnt: "Abgelehnt",
  leer: "Ohne Anhang",
  fehler: "Fehler",
};

export const STATUS_TONE: Record<string, "success" | "warning" | "danger" | "neutral"> = {
  verarbeitet: "success",
  abgelehnt: "warning",
  leer: "neutral",
  fehler: "danger",
};
