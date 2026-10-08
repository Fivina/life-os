import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { expect, it } from "vitest";
import { LegacyChatRedirect } from "../features/assistant/LegacyChatRedirect";

function Destination() {
  const location = useLocation();
  return <output>{JSON.stringify({ path: location.pathname + location.search + location.hash, state: location.state })}</output>;
}

it.each(["/self", "/self/assistant", "/assistant"])("preserves saved conversation and draft/context on %s", path => {
  const state = { phengosOriginLayer: "overview", draft: "unsent", role: "CHEF" };
  render(<MemoryRouter initialEntries={[{ pathname: path, search: "?thread=saved%2Fthread&q=unsent", hash: "#message", state }]}>
    <Routes><Route path={path} element={<LegacyChatRedirect />} /><Route path="/chat" element={<Destination />} /></Routes>
  </MemoryRouter>);
  expect(screen.getByRole("status").textContent).toBe(JSON.stringify({ path: "/chat?thread=saved%2Fthread&q=unsent#message", state }));
});
