import { describe, expect, it } from "vitest";

import { moveSelection, reviewKeyFor, selectionAfterRemove } from "./helpers";

const key = (k: string, mods: Partial<{ metaKey: boolean; ctrlKey: boolean; altKey: boolean; shiftKey: boolean }> = {}) => ({
  key: k,
  metaKey: false,
  ctrlKey: false,
  altKey: false,
  shiftKey: false,
  ...mods,
});

describe("review keyboard (B-14)", () => {
  it("maps j/k/a/r and arrows, ignores modified keys", () => {
    expect(reviewKeyFor(key("j"))).toBe("next");
    expect(reviewKeyFor(key("ArrowUp"))).toBe("prev");
    expect(reviewKeyFor(key("a"))).toBe("approve");
    expect(reviewKeyFor(key("r"))).toBe("reject");
    expect(reviewKeyFor(key("A", { shiftKey: true }))).toBeNull(); // the assistant's key
    expect(reviewKeyFor(key("a", { metaKey: true }))).toBeNull();
    expect(reviewKeyFor(key("x"))).toBeNull();
  });

  it("moves within bounds and starts at the top", () => {
    expect(moveSelection(-1, "next", 3)).toBe(0);
    expect(moveSelection(-1, "prev", 3)).toBe(0);
    expect(moveSelection(2, "next", 3)).toBe(2);
    expect(moveSelection(0, "prev", 3)).toBe(0);
    expect(moveSelection(1, "next", 3)).toBe(2);
    expect(moveSelection(0, "next", 0)).toBe(-1);
  });

  it("keeps the cursor on the row that slides into the gap after a decision", () => {
    expect(selectionAfterRemove(1, 1, 3)).toBe(1); // next row takes its place
    expect(selectionAfterRemove(2, 2, 3)).toBe(1); // last row removed → new last
    expect(selectionAfterRemove(2, 0, 3)).toBe(1); // row above removed → shift up
    expect(selectionAfterRemove(0, 0, 1)).toBe(-1); // list empty
  });
});
