import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { MoviesPage } from "../features/movies/MoviesPage";
import { api } from "../services/api";

vi.mock("../services/api", () => ({ api: {
  leisureTrajectory: vi.fn(), updateLeisureTrajectory: vi.fn(), movies: vi.fn(), createMovie: vi.fn(),
  movieWatchlist: vi.fn(), addMovieToWatchlist: vi.fn(), removeMovieFromWatchlist: vi.fn(),
  movieHistory: vi.fn(), markMovieWatched: vi.fn(), recommendMovies: vi.fn(), recordMovieOutcome: vi.fn(),
  previewLetterboxdImport: vi.fn(), confirmMovieImport: vi.fn(), resolveMovieImportRow: vi.fn()
} }));

const mockedApi = vi.mocked(api);

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}><MoviesPage /></QueryClientProvider>);
}

describe("v1.8B cinema workspace", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedApi.leisureTrajectory.mockResolvedValue({ id: "t1", leisure_type: "MOVIE", period: "WEEK", target_min: 2, target_max: 3, week_starts_on: 0, status: "ACTIVE", period_start: "2026-09-21T00:00:00Z", period_end: "2026-09-28T00:00:00Z", completed_count: 1, state: "BELOW_RANGE", remaining_to_min: 1 });
    mockedApi.movies.mockResolvedValue([]);
    mockedApi.movieWatchlist.mockResolvedValue([]);
    mockedApi.movieHistory.mockResolvedValue([]);
  });

  it("shows the weekly range without framing it as debt", async () => {
    renderPage();
    expect(await screen.findByText(/1 watched · comfortable range 2–3/i)).toBeInTheDocument();
    expect(screen.queryByText(/debt|behind|overdue/i)).not.toBeInTheDocument();
  });

  it("keeps choosing and watching as separate outcomes", async () => {
    mockedApi.recommendMovies.mockResolvedValue({
      id: "r1", domain: "leisure", kind: "movie", title: "Movies for this moment", status: "created", created_at: "2026-09-27T18:00:00Z", context_snapshot: {},
      options: [{ id: "o1", label: "Arrival", rank: 1, score: 42, reference_type: "movie", reference_id: "m1", payload_json: { movie_id: "m1", runtime_minutes: 116, genres: ["Drama"], score_factors: { watchlist: 30 }, explanation: ["Already on your watchlist"] } }]
    });
    mockedApi.recordMovieOutcome.mockResolvedValue({});
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: /recommend/i }));
    expect(await screen.findByText("Arrival")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Choose Arrival" }));
    await waitFor(() => expect(mockedApi.recordMovieOutcome).toHaveBeenCalledWith("r1", "o1", "SELECTED"));
    expect(mockedApi.markMovieWatched).not.toHaveBeenCalled();
  });

  it("keeps an import preview when switching between movie tabs", async () => {
    mockedApi.previewLetterboxdImport.mockResolvedValue({ id: "batch-1", provider: "letterboxd_export", file_name: "diary.csv", status: "PREVIEW", summary: { total: 1, ready: 1, review_required: 0 }, confirmed_at: null, rows: [{ id: "row-1", source_kind: "DIARY", source_row_key: "1", status: "READY", error: null, normalized: { title: "Arrival", year: 2016 }, movie_id: "movie-1" }] });
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: /Import/i }));
    const file = new File(["Name,Year\nArrival,2016"], "diary.csv", { type: "text/csv" });
    Object.defineProperty(file, "text", { value: vi.fn().mockResolvedValue("Name,Year\nArrival,2016") });
    fireEvent.change(screen.getByLabelText("Choose Letterboxd CSV"), { target: { files: [file] } });
    expect(await screen.findByText("Arrival")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: /Discover/i }));
    expect(screen.getByText("Arrival")).not.toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: /Import/i }));
    expect(screen.getByText("Arrival")).toBeVisible();
    expect(mockedApi.previewLetterboxdImport).toHaveBeenCalledTimes(1);
  });
});
