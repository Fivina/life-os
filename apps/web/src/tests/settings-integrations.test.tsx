import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { IntegrationsPage } from "../features/settings/IntegrationsPage";
import { api, apiRequest } from "../services/api";
import { integrationsService, type IntegrationProvider } from "../services/integrations";

vi.mock("../services/api", async () => {
  const actual = await vi.importActual<typeof import("../services/api")>("../services/api");
  return {
    ...actual,
    apiRequest: vi.fn(),
    api: {
      ...actual.api,
      movies: vi.fn(),
      previewLetterboxdImport: vi.fn(),
      confirmMovieImport: vi.fn(),
      resolveMovieImportRow: vi.fn()
    }
  };
});

const providers: IntegrationProvider[] = [
  { id: "tmdb", name: "TMDB", kind: "api", configured: false, credential_management_available: true, scope: "tenant", environment: "sandbox", capabilities: [], last_success_at: null, last_attempt_at: null, error_code: null, language: "en", region: "DE", attribution: "This product uses the TMDB API but is not endorsed or certified by TMDB." },
  { id: "plaid", name: "Plaid", kind: "api", configured: false, credential_management_available: true, scope: "tenant", environment: "sandbox", capabilities: [], last_success_at: null, last_attempt_at: null, error_code: null, client_id: "0123456789abcdef01234567" },
  { id: "letterboxd", name: "Letterboxd", kind: "import", configured: false, credential_management_available: false, scope: "tenant", environment: "sandbox", capabilities: [], last_success_at: null, last_attempt_at: null, error_code: null }
];

const mockedApiRequest = vi.mocked(apiRequest);
const mockedApi = vi.mocked(api);

function renderPage(path = "/settings/integrations") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[path]}><Routes><Route path="/settings/integrations/:provider?" element={<IntegrationsPage />} /></Routes></MemoryRouter></QueryClientProvider>);
}

function mockIntegrationRequests(items = providers, available = true) {
  mockedApiRequest.mockImplementation(async (path, options) => {
    if (path.startsWith("/settings/integrations?") && !options) return { providers: items, credential_management_available: available };
    if (options?.method === "PUT") return { provider: "tmdb", configured: true, scope: "tenant" };
    if (options?.method === "DELETE") return { provider: "tmdb", configured: false, scope: "tenant" };
    if (options?.method === "POST") return { provider: "tmdb", configured: true, scope: "tenant", success: true, error_code: null, last_attempt_at: "2026-10-08T10:00:00Z", last_success_at: "2026-10-08T10:00:00Z" };
    throw new Error(`Unexpected request: ${path}`);
  });
}

describe("settings integrations", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedApi.movies.mockResolvedValue([]);
    mockIntegrationRequests();
  });

  it("shows missing API credentials and routes Letterboxd to the Settings importer", async () => {
    renderPage();
    expect((await screen.findAllByText("Missing")).length).toBe(2);
    expect(screen.getAllByText("Import source").length).toBe(2);
    expect(screen.getByRole("link", { name: "Import from Letterboxd" })).toHaveAttribute("href", "/settings/integrations/letterboxd");
  });

  it("clears the write-only secret and preserves unchanged metadata on replacement", async () => {
    renderPage();
    const input = await screen.findByLabelText("New TMDB API key");
    fireEvent.change(input, { target: { value: "secret-value-long-enough" } });
    fireEvent.click(within(input.closest("article") as HTMLElement).getByRole("button", { name: "Save credential" }));
    await waitFor(() => expect(input).toHaveValue(""));
    const saveCall = mockedApiRequest.mock.calls.find(([, options]) => options?.method === "PUT");
    expect(saveCall?.[0]).toBe("/settings/integrations/tmdb/credentials");
    expect(JSON.parse(String(saveCall?.[1]?.body))).toEqual({ api_key: "secret-value-long-enough", scope: "tenant" });
  });

  it("sends null when the user explicitly clears saved metadata", async () => {
    renderPage();
    const key = await screen.findByLabelText("New TMDB API key");
    fireEvent.change(screen.getByLabelText("TMDB language"), { target: { value: "" } });
    fireEvent.change(screen.getByLabelText("TMDB region"), { target: { value: "" } });
    fireEvent.change(key, { target: { value: "secret-value-long-enough" } });
    fireEvent.click(within(key.closest("article") as HTMLElement).getByRole("button", { name: "Save credential" }));
    await waitFor(() => expect(key).toHaveValue(""));
    const saveCall = mockedApiRequest.mock.calls.find(([, options]) => options?.method === "PUT");
    expect(JSON.parse(String(saveCall?.[1]?.body))).toEqual({ api_key: "secret-value-long-enough", scope: "tenant", language: null, region: null });
  });

  it("uses server metadata as the Plaid client ID default", async () => {
    renderPage();
    expect(await screen.findByLabelText("Plaid client ID")).toHaveValue("0123456789abcdef01234567");
  });

  it("sends null when the saved Plaid client ID is explicitly cleared", async () => {
    renderPage();
    const key = await screen.findByLabelText("New Plaid API key");
    fireEvent.change(screen.getByLabelText("Plaid client ID"), { target: { value: "" } });
    fireEvent.change(key, { target: { value: "plaid-secret-long-enough" } });
    fireEvent.click(within(key.closest("article") as HTMLElement).getByRole("button", { name: "Save credential" }));
    await waitFor(() => expect(key).toHaveValue(""));
    const saveCall = mockedApiRequest.mock.calls.find(([path, options]) => path.includes("/plaid/") && options?.method === "PUT");
    expect(JSON.parse(String(saveCall?.[1]?.body))).toEqual({ api_key: "plaid-secret-long-enough", scope: "tenant", client_id: null });
  });

  it("disables credential entry when Vault is unavailable", async () => {
    mockIntegrationRequests([{ ...providers[0], credential_management_available: false }], false);
    renderPage();
    expect(await screen.findByRole("status")).toHaveTextContent("Vault storage is unavailable");
    expect(screen.getByLabelText("New TMDB API key")).toBeDisabled();
  });

  it("keeps two provider drafts isolated", async () => {
    renderPage();
    const tmdb = await screen.findByLabelText("New TMDB API key");
    const plaid = screen.getByLabelText("New Plaid API key");
    fireEvent.change(tmdb, { target: { value: "tmdb-secret-long-enough" } });
    fireEvent.change(plaid, { target: { value: "plaid-secret-long-enough" } });
    fireEvent.click(within(tmdb.closest("article") as HTMLElement).getByRole("button", { name: "Save credential" }));
    await waitFor(() => expect(mockedApiRequest).toHaveBeenCalledWith("/settings/integrations/tmdb/credentials", expect.objectContaining({ method: "PUT" })));
    expect(plaid).toHaveValue("plaid-secret-long-enough");
  });

  it("renders an unsuccessful test result as an error", async () => {
    const configured = [{ ...providers[0], configured: true }];
    mockedApiRequest.mockImplementation(async (path, options) => {
      if (!options) return { providers: configured, credential_management_available: true };
      return { provider: "tmdb", configured: true, scope: "tenant", success: false, error_code: "authentication_failed", last_attempt_at: "2026-10-08T10:00:00Z", last_success_at: null };
    });
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: "Test connection" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Connection test failed. The provider rejected the credential.");
    expect(screen.queryByText("Connection test succeeded.")).not.toBeInTheDocument();
  });

  it("fails closed when installation scope is not authorized", async () => {
    mockedApiRequest.mockImplementation(async (path) => {
      if (path.endsWith("scope=tenant")) return { providers, credential_management_available: true };
      throw new Error("backend detail is not rendered");
    });
    renderPage();
    await screen.findByText("TMDB");
    fireEvent.change(screen.getByLabelText("Credential scope"), { target: { value: "installation" } });
    expect(await screen.findByRole("alert")).toHaveTextContent("Installation-scoped access is unavailable for this account.");
    expect(screen.queryByText("backend detail is not rendered")).not.toBeInTheDocument();
  });

  it("previews without importing and confirms only after the user action", async () => {
    mockedApi.previewLetterboxdImport.mockResolvedValue({ id: "batch-1", provider: "letterboxd_export", file_name: "diary.csv", status: "PREVIEW", summary: { total: 1, ready: 1, review_required: 0 }, confirmed_at: null, rows: [{ id: "row-1", source_kind: "DIARY", source_row_key: "1", status: "READY", error: null, normalized: { title: "Arrival", year: 2016 }, movie_id: "movie-1" }] });
    mockedApi.confirmMovieImport.mockResolvedValue({ id: "batch-1", provider: "letterboxd_export", file_name: "diary.csv", status: "CONFIRMED", summary: { total: 1, ready: 0, imported: 1 }, confirmed_at: "2026-10-08T10:00:00Z", rows: [{ id: "row-1", source_kind: "DIARY", source_row_key: "1", status: "IMPORTED", error: null, normalized: { title: "Arrival", year: 2016 }, movie_id: "movie-1" }] });
    renderPage("/settings/integrations/letterboxd");
    expect(await screen.findByRole("heading", { name: "Import from Letterboxd" })).toBeInTheDocument();
    const file = new File(["Name,Year\nArrival,2016"], "diary.csv", { type: "text/csv" });
    Object.defineProperty(file, "text", { value: vi.fn().mockResolvedValue("Name,Year\nArrival,2016") });
    fireEvent.change(screen.getByLabelText("Choose Letterboxd CSV"), { target: { files: [file] } });
    expect(await screen.findByText("Arrival")).toBeInTheDocument();
    expect(mockedApi.confirmMovieImport).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Confirm ready rows" }));
    await waitFor(() => expect(mockedApi.confirmMovieImport).toHaveBeenCalledWith("batch-1"));
  });

  it("lets the backend detect a default watchlist CSV destination from its filename", async () => {
    mockedApi.previewLetterboxdImport.mockResolvedValue({ id: "batch-watchlist", provider: "letterboxd_export", file_name: "watchlist.csv", status: "PREVIEW", summary: { total: 1, ready: 1, review_required: 0 }, confirmed_at: null, rows: [{ id: "row-watchlist", source_kind: "WATCHLIST", source_row_key: "1", status: "READY", error: null, normalized: { title: "Moonlight", year: 2016 }, movie_id: "movie-2" }] });
    renderPage("/settings/integrations/letterboxd");
    expect(await screen.findByLabelText("Letterboxd file type")).toHaveValue("AUTO");
    const file = new File(["Name,Year\nMoonlight,2016"], "watchlist.csv", { type: "text/csv" });
    Object.defineProperty(file, "text", { value: vi.fn().mockResolvedValue("Name,Year\nMoonlight,2016") });
    fireEvent.change(screen.getByLabelText("Choose Letterboxd CSV"), { target: { files: [file] } });
    await waitFor(() => expect(mockedApi.previewLetterboxdImport).toHaveBeenCalledWith({ file_name: "watchlist.csv", content: "Name,Year\nMoonlight,2016" }));
    expect(await screen.findByText("Preview destination: Watchlist")).toBeInTheDocument();
  });

  it("sends an explicit source destination only when the user overrides detection", async () => {
    mockedApi.previewLetterboxdImport.mockResolvedValue({ id: "batch-diary", provider: "letterboxd_export", file_name: "watchlist.csv", status: "PREVIEW", summary: { total: 1, ready: 1, review_required: 0 }, confirmed_at: null, rows: [{ id: "row-diary", source_kind: "DIARY", source_row_key: "1", status: "READY", error: null, normalized: { title: "Moonlight", year: 2016 }, movie_id: "movie-2" }] });
    renderPage("/settings/integrations/letterboxd");
    fireEvent.change(await screen.findByLabelText("Letterboxd file type"), { target: { value: "DIARY" } });
    expect(screen.getByText("Selected destination: Diary")).toBeInTheDocument();
    const file = new File(["Name,Year\nMoonlight,2016"], "watchlist.csv", { type: "text/csv" });
    Object.defineProperty(file, "text", { value: vi.fn().mockResolvedValue("Name,Year\nMoonlight,2016") });
    fireEvent.change(screen.getByLabelText("Choose Letterboxd CSV"), { target: { files: [file] } });
    await waitFor(() => expect(mockedApi.previewLetterboxdImport).toHaveBeenCalledWith({ file_name: "watchlist.csv", content: "Name,Year\nMoonlight,2016", source_kind: "DIARY" }));
    expect(await screen.findByText("Preview destination: Diary")).toBeInTheDocument();
  });

  it("keeps the Letterboxd importer available when integration status fails", async () => {
    mockedApiRequest.mockRejectedValue(new Error("status unavailable"));
    mockedApi.previewLetterboxdImport.mockResolvedValue({ id: "batch-2", provider: "letterboxd_export", file_name: "watchlist.csv", status: "PREVIEW", summary: { total: 1, ready: 1, review_required: 0 }, confirmed_at: null, rows: [{ id: "row-2", source_kind: "WATCHLIST", source_row_key: "1", status: "READY", error: null, normalized: { title: "Moonlight", year: 2016 }, movie_id: "movie-2" }] });
    renderPage("/settings/integrations/letterboxd");
    expect(await screen.findByRole("heading", { name: "Import from Letterboxd" })).toBeInTheDocument();
    const file = new File(["Name,Year\nMoonlight,2016"], "watchlist.csv", { type: "text/csv" });
    Object.defineProperty(file, "text", { value: vi.fn().mockResolvedValue("Name,Year\nMoonlight,2016") });
    fireEvent.change(screen.getByLabelText("Choose Letterboxd CSV"), { target: { files: [file] } });
    expect(await screen.findByText("Moonlight")).toBeInTheDocument();
    expect(mockedApi.previewLetterboxdImport).toHaveBeenCalledTimes(1);
    expect(mockedApiRequest).not.toHaveBeenCalled();
  });
});

describe("integration endpoint boundaries", () => {
  beforeEach(() => vi.clearAllMocks());

  it("uses the plural credentials route and preserves explicit scopes", async () => {
    mockedApiRequest.mockResolvedValue({ provider: "tmdb", configured: true, scope: "installation" });
    await integrationsService.saveCredential("tmdb", { api_key: "secret-value-long-enough", scope: "installation" });
    await integrationsService.removeCredential("tmdb", "installation");
    await integrationsService.test("tmdb", "installation");
    expect(mockedApiRequest).toHaveBeenNthCalledWith(1, "/settings/integrations/tmdb/credentials", expect.objectContaining({ method: "PUT", body: JSON.stringify({ api_key: "secret-value-long-enough", scope: "installation" }) }));
    expect(mockedApiRequest).toHaveBeenNthCalledWith(2, "/settings/integrations/tmdb/credentials?scope=installation", { method: "DELETE" });
    expect(mockedApiRequest).toHaveBeenNthCalledWith(3, "/settings/integrations/tmdb/test?scope=installation", { method: "POST" });
  });
});
