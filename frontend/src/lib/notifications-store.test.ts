// @vitest-environment jsdom
import { beforeEach, describe, expect, it } from "vitest";

import { buildNotifications, useNotificationsStore } from "./notifications-store";

describe("notifications from system signals (B-16)", () => {
  beforeEach(() => {
    localStorage.clear();
    useNotificationsStore.setState({ items: [] });
  });

  it("builds one item per signal, review count from a list or a count", () => {
    const fromList = buildNotifications({ review: [1, 2, 3], info: null, aiStatus: null, stats: null }, 0);
    expect(fromList.map((i) => i.id)).toEqual(["review-3"]);
    const all = buildNotifications(
      { review: { count: 1 }, info: { has_model: false }, aiStatus: { ok: false }, stats: { total_count: 5, total_amount: 12.5 } },
      0,
    );
    expect(all.map((i) => i.id)).toEqual(["review-1", "model-untrained", "ollama-offline", "bookings-5"]);
    expect(all[3].body).toContain("CHF 12.50");
  });

  it("keeps read state across polls and keeps the same reference when nothing changed", () => {
    const store = useNotificationsStore.getState();
    const sources = { review: [1], info: { has_model: true, model_accuracy: 0.9 }, aiStatus: { ok: true }, stats: null };
    store.setFromSources(sources);
    store.markRead("review-1");
    const before = useNotificationsStore.getState().items;
    expect(before.find((i) => i.id === "review-1")?.read).toBe(true);
    expect(useNotificationsStore.getState().unreadCount()).toBe(1);

    useNotificationsStore.getState().setFromSources(sources);
    expect(useNotificationsStore.getState().items).toBe(before);

    useNotificationsStore.getState().setFromSources({ ...sources, review: [1, 2] });
    expect(useNotificationsStore.getState().items.map((i) => i.id)).toEqual(["review-2", "model-acc-90"]);
  });
});
