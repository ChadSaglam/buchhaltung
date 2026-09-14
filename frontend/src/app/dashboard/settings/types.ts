import type { UserResponse } from "@/lib/api-schema";

export type UserInfo = UserResponse;

export type TabId = "profile" | "company" | "review" | "appearance";

export interface Tab {
  id: TabId;
  label: string;
  icon: React.ElementType;
}
