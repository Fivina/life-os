import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { NotebookPage } from "../features/notebook/NotebookPage";
import { api } from "../services/api";

vi.mock("../services/api", () => ({ api: {
  notebookEntries: vi.fn(), searchNotebook: vi.fn(), createNotebookEntry: vi.fn(),
  reviewNotebookEntry: vi.fn(), archiveNotebookEntry: vi.fn(), promoteNotebookEntry: vi.fn()
} }));

const mockedApi = vi.mocked(api);

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}><NotebookPage /></QueryClientProvider>);
}

describe("v1.8A notebook", () => {
  beforeEach(() => { vi.clearAllMocks(); mockedApi.notebookEntries.mockResolvedValue([]); });

  it("captures an implementation idea without task controls", async () => {
    mockedApi.createNotebookEntry.mockResolvedValue({ id: "n1", entry_type: "IMPLEMENTATION_IDEA", title: "Quiet review", content: "Add quiet review", status: "ACTIVE", source: "manual", tags_json: [], created_at: "2026-09-26T08:00:00Z", updated_at: "2026-09-26T08:00:00Z", version: 1 });
    renderPage();
    fireEvent.change(screen.getByLabelText("Title"), { target: { value: "Quiet review" } });
    fireEvent.change(screen.getByLabelText("Content"), { target: { value: "Add quiet review" } });
    fireEvent.click(screen.getByRole("button", { name: "Save entry" }));
    await waitFor(() => expect(mockedApi.createNotebookEntry.mock.calls[0]?.[0]).toEqual(expect.objectContaining({ entry_type: "IMPLEMENTATION_IDEA" })));
    expect(screen.queryByText(/create task/i)).not.toBeInTheDocument();
  });
});
