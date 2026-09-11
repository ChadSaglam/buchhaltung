// @vitest-environment jsdom
import { describe, expect, it, vi, afterEach } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { EmptyState } from "./EmptyState";
import { ErrorState } from "./ErrorState";
import { PageSkeleton } from "./PageSkeleton";

afterEach(cleanup);

describe("EmptyState", () => {
  it("renders title, description and the primary action", () => {
    render(<EmptyState title="Keine Einträge" description="Noch nichts da." action={<button>Anlegen</button>} />);
    expect(screen.getByRole("status", { name: "Keine Einträge" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Keine Einträge" })).toBeTruthy();
    expect(screen.getByText("Noch nichts da.")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Anlegen" })).toBeTruthy();
  });

  it("omits description and action when not given", () => {
    render(<EmptyState title="Leer" />);
    expect(screen.queryByRole("button")).toBeNull();
    expect(screen.getByRole("status").querySelector("p")).toBeNull();
  });
});

describe("ErrorState", () => {
  const envelope = {
    response: {
      status: 503,
      data: { error: { code: "upstream_down", message: "Ollama ist nicht erreichbar.", request_id: "req-42" } },
    },
  };

  it("shows the envelope message and request id as an alert", () => {
    render(<ErrorState error={envelope} />);
    const alert = screen.getByRole("alert");
    expect(alert.textContent).toContain("Ollama ist nicht erreichbar.");
    expect(alert.textContent).toContain("req-42");
    expect(screen.getByRole("heading", { name: "Das hat nicht geklappt" })).toBeTruthy();
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("falls back to the status text when there is no envelope", () => {
    render(<ErrorState error={{ response: { status: 404 } }} />);
    expect(screen.getByRole("alert").textContent).toContain("Nicht gefunden");
  });

  it("calls onRetry from the retry button (page and inline)", () => {
    const onRetry = vi.fn();
    const { unmount } = render(<ErrorState error={envelope} onRetry={onRetry} />);
    fireEvent.click(screen.getByRole("button", { name: "Erneut versuchen" }));
    expect(onRetry).toHaveBeenCalledTimes(1);
    unmount();

    render(<ErrorState error={envelope} onRetry={onRetry} variant="inline" title="Scan" />);
    expect(screen.getByRole("alert").textContent).toContain("Scan: Ollama ist nicht erreichbar.");
    fireEvent.click(screen.getByRole("button", { name: "Erneut versuchen" }));
    expect(onRetry).toHaveBeenCalledTimes(2);
  });
});

describe("PageSkeleton", () => {
  it("announces loading and renders the requested shapes", () => {
    const { container } = render(<PageSkeleton header metrics={3} rows={2} />);
    const root = screen.getByTestId("page-skeleton");
    expect(root.getAttribute("aria-busy")).toBe("true");
    expect(screen.getByText("Laden...").className).toContain("sr-only");
    // 2 header bars + 3 metric cards × 3 bars + 1 table title + 2 rows
    expect(container.querySelectorAll(".animate-pulse").length).toBe(2 + 9 + 1 + 2);
  });

  it("renders nothing but the live region when every count is zero", () => {
    const { container } = render(<PageSkeleton metrics={0} rows={0} />);
    expect(container.querySelectorAll(".animate-pulse").length).toBe(0);
  });
});
