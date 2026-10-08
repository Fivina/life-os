import { render, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { RouteSectionFocus } from "./RouteSectionFocus";

describe("workspace section navigation", () => {
  it("focuses the actual selected section without changing its data", async () => {
    const result = render(<MemoryRouter initialEntries={["/kitchen#shopping"]}>
      <RouteSectionFocus /><h2 id="shopping" tabIndex={-1}>Shopping List</h2>
    </MemoryRouter>);
    await waitFor(() => expect(result.getByText("Shopping List")).toHaveFocus());
  });
  it("ignores malformed hashes safely", () => {
    expect(() => render(<MemoryRouter initialEntries={["/kitchen#%ZZ"]}><RouteSectionFocus /></MemoryRouter>)).not.toThrow();
  });
});
