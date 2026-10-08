import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ConnectionStatusBanner } from "../layouts/AppShell";


describe("connection recovery state", () => {
  it("stays quiet while live and explains stale state while reconnecting", () => {
    const { rerender } = render(<ConnectionStatusBanner state="LIVE" />);
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    rerender(<ConnectionStatusBanner state="RECONNECTING" />);
    expect(screen.getByRole("status")).toHaveTextContent("last confirmed state");
    expect(screen.getByRole("button", { name: "Refresh connection" })).toBeEnabled();
  });

  it("does not claim writes succeeded while offline", () => {
    render(<ConnectionStatusBanner state="OFFLINE" />);
    expect(screen.getByRole("status")).toHaveTextContent("Changes are not being sent");
  });
});
