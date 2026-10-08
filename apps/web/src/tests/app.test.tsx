import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { App } from "../app/App";

describe("Life OS app shell", () => {
  it("renders the private login screen by default", async () => {
    render(<App />);
    expect(screen.getByRole("heading", { name: "Life OS" })).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: /enter/i })).toBeInTheDocument();
  });
});
