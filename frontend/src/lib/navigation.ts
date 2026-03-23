import {
  LayoutDashboard, FileText, ScanLine, BookOpen,
  Brain, GraduationCap, Settings, LogOut
} from "lucide-react";
import { type LucideIcon } from "lucide-react";

export interface NavItem {
  label: string;
  href: string;
  icon: LucideIcon;
  badge?: string;
  section?: string;
}

export const NAV_ITEMS: NavItem[] = [
  { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard, section: "Übersicht" },
  { label: "Kontoauszug", href: "/dashboard/kontoauszug", icon: FileText, section: "Buchhaltung" },
  { label: "Scanner", href: "/dashboard/scanner", icon: ScanLine, section: "Buchhaltung" },
  { label: "Kontenplan", href: "/dashboard/kontenplan", icon: BookOpen, section: "AI & Training" },
  { label: "Modell", href: "/dashboard/modell", icon: Brain, section: "AI & Training" },
  { label: "Lernverlauf", href: "/dashboard/lernverlauf", icon: GraduationCap, section: "AI & Training" },
  { label: "Einstellungen", href: "/dashboard/settings", icon: Settings, section: "System" },
];

export function getNavSections() {
  const sections = new Map<string, NavItem[]>();
  for (const item of NAV_ITEMS) {
    const key = item.section ?? "Allgemein";
    if (!sections.has(key)) sections.set(key, []);
    sections.get(key)!.push(item);
  }
  return sections;
}
