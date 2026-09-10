import { User, Building2, Bell, Palette, Shield, SlidersHorizontal, Sun, Moon, Monitor } from "lucide-react";
import type { Theme } from "@/lib/theme-store";
import type { Tab } from "./types";

export const THEME_OPTIONS: { id: Theme; label: string; icon: React.ElementType }[] = [
  { id: "light", label: "Hell", icon: Sun },
  { id: "dark", label: "Dunkel", icon: Moon },
  { id: "system", label: "System", icon: Monitor },
];

export const TABS: Tab[] = [
  { id: "profile", label: "Profil", icon: User },
  { id: "company", label: "Unternehmen", icon: Building2 },
  { id: "review", label: "Überprüfung", icon: SlidersHorizontal },
  { id: "notifications", label: "Benachrichtigungen", icon: Bell },
  { id: "appearance", label: "Darstellung", icon: Palette },
  { id: "security", label: "Sicherheit", icon: Shield },
];
