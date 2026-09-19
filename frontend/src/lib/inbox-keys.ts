/**
 * Keyboard model shared by every decision list (Überprüfung, Abgleich, …):
 * j/k or arrows move, a accepts, r rejects. One keyboard everywhere (IA rule).
 */
export type InboxKey = "next" | "prev" | "approve" | "reject";

export function inboxKeyFor(e: {
  key: string;
  metaKey: boolean;
  ctrlKey: boolean;
  altKey: boolean;
  shiftKey: boolean;
}): InboxKey | null {
  if (e.metaKey || e.ctrlKey || e.altKey || e.shiftKey) return null;
  switch (e.key) {
    case "j":
    case "ArrowDown":
      return "next";
    case "k":
    case "ArrowUp":
      return "prev";
    case "a":
      return "approve";
    case "r":
      return "reject";
    default:
      return null;
  }
}

/** Index after a move; clamps to the list, -1 stays -1 on an empty list. */
export function moveSelection(index: number, dir: "next" | "prev", length: number): number {
  if (length === 0) return -1;
  if (index < 0) return 0;
  const next = dir === "next" ? index + 1 : index - 1;
  return Math.min(Math.max(next, 0), length - 1);
}

/** Selection after removing `removedIndex` from a list that had `length` entries. */
export function selectionAfterRemove(index: number, removedIndex: number, length: number): number {
  const remaining = length - 1;
  if (remaining <= 0) return -1;
  if (index > removedIndex) return index - 1;
  return Math.min(index, remaining - 1);
}
