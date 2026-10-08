import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { useState } from "react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import { ContextualAssistantLauncher } from "../features/phengos/navigation/ContextualAssistantLauncher";

vi.mock("../features/assistant/AssistantPage", () => ({
  AssistantPage: ({ onOpenFullChat }: { onOpenFullChat: (id: string) => void }) => {
    const [draft, setDraft] = useState("");
    return <div className="assistant-shell"><textarea aria-label="Message" value={draft} onChange={event => setDraft(event.target.value)} />
      <button onClick={() => onOpenFullChat("canonical/thread")}>Continue in Chat</button></div>;
  }
}));

let media: { matches: boolean; addEventListener: ReturnType<typeof vi.fn>; removeEventListener: ReturnType<typeof vi.fn> };
let onResize: (() => void) | undefined;
const descriptors = new Map<string, PropertyDescriptor | undefined>();

beforeEach(() => {
  media = { matches: false, addEventListener: vi.fn((_event, listener) => { onResize = listener; }), removeEventListener: vi.fn() };
  vi.stubGlobal("matchMedia", vi.fn(() => media));
  for (const method of ["show", "showModal", "close"] as const) {
    descriptors.set(method, Object.getOwnPropertyDescriptor(HTMLDialogElement.prototype, method));
    Object.defineProperty(HTMLDialogElement.prototype, method, { configurable: true, value: vi.fn(function (this: HTMLDialogElement) {
      if (method === "close") this.removeAttribute("open");
      else { this.setAttribute("open", ""); this.dataset.modal = String(method === "showModal"); }
    }) });
  }
});
afterEach(() => {
  vi.unstubAllGlobals();
  for (const [method, descriptor] of descriptors) {
    if (descriptor) Object.defineProperty(HTMLDialogElement.prototype, method, descriptor);
    else Reflect.deleteProperty(HTMLDialogElement.prototype, method);
  }
  onResize = undefined;
});

function Location() { const location = useLocation(); return <output>{location.pathname + location.search + location.hash}</output>; }
function setup() {
  return render(<MemoryRouter initialEntries={["/calendar?commitment=saved#day"]}>
    <ContextualAssistantLauncher workspace="calendar" /><Location />
  </MemoryRouter>);
}

it("keeps the workspace URL and mounted conversation draft through minimize, close and Escape", () => {
  setup();
  fireEvent.click(screen.getByRole("button", { name: "Open Calendar chat" }));
  fireEvent.change(screen.getByRole("textbox", { name: "Message" }), { target: { value: "Unsent thought" } });
  fireEvent.click(screen.getByRole("button", { name: "Minimize chat" }));
  const launcher = screen.getByRole("button", { name: "Open Calendar chat" });
  expect(launcher).toHaveFocus();
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  fireEvent.click(launcher);
  expect(screen.getByRole("textbox", { name: "Message" })).toHaveValue("Unsent thought");
  fireEvent.click(screen.getByRole("button", { name: "Close chat" }));
  fireEvent.click(launcher);
  fireEvent.keyDown(screen.getByRole("textbox", { name: "Message" }), { key: "Escape" });
  expect(launcher).toHaveFocus();
  expect(screen.getByRole("status")).toHaveTextContent("/calendar?commitment=saved#day");
});

it("uses a mobile modal sheet and switches presentation without clearing the draft", () => {
  media.matches = true;
  setup();
  fireEvent.click(screen.getByRole("button", { name: "Open Calendar chat" }));
  const dialog = screen.getByRole("dialog", { name: "Calendar chat" });
  expect(dialog).toHaveAttribute("aria-modal", "true");
  expect(dialog).toHaveAttribute("data-modal", "true");
  fireEvent.change(within(dialog).getByRole("textbox"), { target: { value: "Keep me" } });
  media.matches = false;
  act(() => onResize?.());
  expect(dialog).not.toHaveAttribute("aria-modal");
  expect(dialog).toHaveAttribute("data-modal", "false");
  expect(screen.getByRole("textbox")).toHaveValue("Keep me");
});

it("opens the canonical thread in full Chat only on the explicit action", () => {
  setup();
  fireEvent.click(screen.getByRole("button", { name: "Open Calendar chat" }));
  fireEvent.click(screen.getByRole("button", { name: "Continue in Chat" }));
  expect(screen.getByRole("status")).toHaveTextContent("/chat?thread=canonical%2Fthread");
});
