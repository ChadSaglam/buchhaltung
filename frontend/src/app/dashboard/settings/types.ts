import type { UserResponse } from "@/lib/api-schema";

export type UserInfo = UserResponse;

export type TabId = "profile" | "company" | "notifications" | "appearance" | "security" | "review";

export interface Tab {
  id: TabId;
  label: string;
  icon: React.ElementType;
}
