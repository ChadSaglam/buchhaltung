// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from "vitest";

const mutate = vi.fn();
vi.mock("swr", () => ({ mutate: (...args: unknown[]) => mutate(...args) }));
vi.mock("@/lib/api", () => ({ default: { get: vi.fn() } }));

import { useAuthStore } from "./auth-store";
import { useNotificationsStore } from "./notifications-store";
import { apiKey, currentUserKey } from "@/hooks/useApi";

describe("logout (B-44)", () => {
  beforeEach(() => {
    localStorage.clear();
    mutate.mockClear();
  });

  it("drops the SWR cache and the notification items, not only the token", () => {
    useAuthStore.getState().setAuth("t0k", { id: 7, email: "a@b.ch", name: "A", role: "owner", tenant_id: 1 } as never);
    useNotificationsStore.setState({ items: [{ id: "x", kind: "review", title: "", body: "", ts: 0, read: false }] });

    useAuthStore.getState().logout();

    expect(localStorage.getItem("token")).toBeNull();
    expect(useNotificationsStore.getState().items).toEqual([]);
    expect(mutate).toHaveBeenCalledTimes(1);
    const [filter, value, opts] = mutate.mock.calls[0];
    expect(typeof filter).toBe("function");
    expect((filter as () => boolean)()).toBe(true); // every key
    expect(value).toBeUndefined();
    expect(opts).toEqual({ revalidate: false });
  });

  it("scopes SWR keys to the signed-in user", () => {
    expect(currentUserKey()).toBe("");
    localStorage.setItem("user", JSON.stringify({ id: 42 }));
    expect(currentUserKey()).toBe("42");
    expect(apiKey("/api/bookings/stats", "42")).toEqual(["/api/bookings/stats", "42"]);
    localStorage.setItem("user", "{not json");
    expect(currentUserKey()).toBe("");
  });
});
