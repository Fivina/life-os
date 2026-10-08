import { Archive, Check, Clock3, Film, Plus, Search, Sparkles, Star, Upload, X } from "lucide-react";
import { type FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../../services/api";
import type { MovieImportBatch, MovieRecommendation } from "../../types/api";


type View = "discover" | "watchlist" | "history" | "import";

export function MoviesPage() {
  const queryClient = useQueryClient();
  const [view, setView] = useState<View>("discover");
  const [query, setQuery] = useState("");
  const [title, setTitle] = useState("");
  const [year, setYear] = useState("");
  const [runtime, setRuntime] = useState("");
  const [genres, setGenres] = useState("");
  const [availableMinutes, setAvailableMinutes] = useState("140");
  const [mood, setMood] = useState("ANY");
  const [preferredGenres, setPreferredGenres] = useState("");
  const [importBatch, setImportBatch] = useState<MovieImportBatch | null>(null);
  const [importKind, setImportKind] = useState("DIARY");
  const [resolutionMovie, setResolutionMovie] = useState<Record<string, string>>({});

  const trajectory = useQuery({ queryKey: ["leisure-trajectory"], queryFn: api.leisureTrajectory });
  const movies = useQuery({ queryKey: ["movies", query], queryFn: () => api.movies(query) });
  const watchlist = useQuery({ queryKey: ["movie-watchlist"], queryFn: api.movieWatchlist });
  const history = useQuery({ queryKey: ["movie-history"], queryFn: api.movieHistory });
  const refreshMovies = () => {
    void queryClient.invalidateQueries({ queryKey: ["movies"] });
    void queryClient.invalidateQueries({ queryKey: ["movie-watchlist"] });
    void queryClient.invalidateQueries({ queryKey: ["movie-history"] });
    void queryClient.invalidateQueries({ queryKey: ["leisure-trajectory"] });
  };
  const createMovie = useMutation({
    mutationFn: api.createMovie,
    onSuccess: () => { setTitle(""); setYear(""); setRuntime(""); setGenres(""); refreshMovies(); }
  });
  const addWatchlist = useMutation({ mutationFn: api.addMovieToWatchlist, onSuccess: refreshMovies });
  const removeWatchlist = useMutation({ mutationFn: api.removeMovieFromWatchlist, onSuccess: refreshMovies });
  const watched = useMutation({
    mutationFn: (movieId: string) => api.markMovieWatched({ movie_id: movieId, watched_at: new Date().toISOString() }),
    onSuccess: refreshMovies
  });
  const recommend = useMutation({ mutationFn: api.recommendMovies });
  const outcome = useMutation({
    mutationFn: ({ recommendation, optionId, result }: { recommendation: MovieRecommendation; optionId: string; result: "SELECTED" | "WATCHED" | "REJECTED" }) => api.recordMovieOutcome(recommendation.id, optionId, result),
    onSuccess: refreshMovies
  });
  const updateTrajectory = useMutation({
    mutationFn: api.updateLeisureTrajectory,
    onSuccess: (data) => queryClient.setQueryData(["leisure-trajectory"], data)
  });
  const previewImport = useMutation({
    mutationFn: api.previewLetterboxdImport,
    onSuccess: setImportBatch
  });
  const confirmImport = useMutation({
    mutationFn: api.confirmMovieImport,
    onSuccess: (data) => { setImportBatch(data); refreshMovies(); }
  });
  const resolveImport = useMutation({
    mutationFn: ({ rowId, movieId }: { rowId: string; movieId: string }) => api.resolveMovieImportRow(rowId, movieId),
    onSuccess: (_, variables) => setImportBatch((current) => current ? { ...current, rows: current.rows.map((row) => row.id === variables.rowId ? { ...row, status: "READY", error: null, movie_id: variables.movieId } : row) } : current)
  });

  function submitMovie(event: FormEvent) {
    event.preventDefault();
    if (!title.trim()) return;
    createMovie.mutate({
      title: title.trim(),
      release_year: year ? Number(year) : null,
      runtime_minutes: runtime ? Number(runtime) : null,
      genres: genres.split(",").map((item) => item.trim()).filter(Boolean)
    });
  }

  async function readImport(file?: File) {
    if (!file) return;
    previewImport.mutate({ file_name: file.name, content: await file.text(), source_kind: importKind });
  }

  const trajectoryValue = trajectory.data;
  const recommendation = recommend.data;

  return <div className="stack movies-page">
    <section className="movie-command-band">
      <div>
        <p className="eyebrow">Leisure trajectory</p>
        <h2>Movies this week</h2>
        <p className="trajectory-copy">{trajectoryValue ? `${trajectoryValue.completed_count} watched · comfortable range ${trajectoryValue.target_min}–${trajectoryValue.target_max}` : "Loading this week…"}</p>
      </div>
      {trajectoryValue ? <div className="trajectory-controls" aria-label="Weekly movie range">
        <label>Minimum<input aria-label="Weekly minimum" type="number" min="0" max="21" value={trajectoryValue.target_min} onChange={(event) => updateTrajectory.mutate({ target_min: Number(event.target.value), target_max: Math.max(Number(event.target.value), trajectoryValue.target_max), week_starts_on: trajectoryValue.week_starts_on, status: trajectoryValue.status })} /></label>
        <label>Maximum<input aria-label="Weekly maximum" type="number" min={trajectoryValue.target_min} max="21" value={trajectoryValue.target_max} onChange={(event) => updateTrajectory.mutate({ target_min: trajectoryValue.target_min, target_max: Number(event.target.value), week_starts_on: trajectoryValue.week_starts_on, status: trajectoryValue.status })} /></label>
      </div> : null}
    </section>

    <nav className="segmented-control movie-tabs" aria-label="Cinema views">
      <button className={view === "discover" ? "active" : ""} onClick={() => setView("discover")}><Sparkles size={15} /> Discover</button>
      <button className={view === "watchlist" ? "active" : ""} onClick={() => setView("watchlist")}><Film size={15} /> Watchlist</button>
      <button className={view === "history" ? "active" : ""} onClick={() => setView("history")}><Clock3 size={15} /> History</button>
      <button className={view === "import" ? "active" : ""} onClick={() => setView("import")}><Upload size={15} /> Import</button>
    </nav>

    {view === "discover" ? <>
      <section className="content-band movie-recommend-controls">
        <div className="section-header"><h2>Choose for tonight</h2><span>3–5 grounded options</span></div>
        <div className="movie-filter-row">
          <label>Time available<input aria-label="Time available in minutes" type="number" min="20" max="1000" value={availableMinutes} onChange={(event) => setAvailableMinutes(event.target.value)} /></label>
          <label>Mood<select aria-label="Movie mood" value={mood} onChange={(event) => setMood(event.target.value)}><option value="ANY">Any</option><option value="LIGHT">Light</option><option value="ENERGETIC">Energetic</option><option value="TENSE">Tense</option><option value="REFLECTIVE">Reflective</option></select></label>
          <label>Genres<input aria-label="Preferred genres" placeholder="Comedy, Drama" value={preferredGenres} onChange={(event) => setPreferredGenres(event.target.value)} /></label>
          <button className="primary-button" onClick={() => recommend.mutate({ available_minutes: Number(availableMinutes), mood, preferred_genres: preferredGenres.split(",").map((item) => item.trim()).filter(Boolean), limit: 5 })} disabled={recommend.isPending}><Sparkles size={16} /> Recommend</button>
        </div>
        {recommendation ? <div className="recommendation-list">{recommendation.options.map((option) => <article className="movie-option" key={option.id}>
          <Poster title={option.label} src={option.payload_json.poster_url} />
          <div className="movie-option-copy"><small>#{option.rank} · {option.payload_json.runtime_minutes ? `${option.payload_json.runtime_minutes} min` : "runtime unknown"}</small><strong>{option.label}</strong><div className="genre-line">{option.payload_json.genres.join(" · ") || "No genres yet"}</div><ul>{option.payload_json.explanation.map((reason) => <li key={reason}>{reason}</li>)}</ul></div>
          <div className="movie-option-actions"><button className="icon-button" title="Choose" aria-label={`Choose ${option.label}`} onClick={() => outcome.mutate({ recommendation, optionId: option.id, result: "SELECTED" })}><Check size={17} /></button><button className="icon-button" title="Mark watched" aria-label={`Mark ${option.label} watched`} onClick={() => outcome.mutate({ recommendation, optionId: option.id, result: "WATCHED" })}><Star size={17} /></button><button className="icon-button" title="Not for me" aria-label={`Reject ${option.label}`} onClick={() => outcome.mutate({ recommendation, optionId: option.id, result: "REJECTED" })}><X size={17} /></button></div>
        </article>)}</div> : null}
        {!recommend.isPending && recommendation?.options.length === 0 ? <p className="status-text">Add a few films or watchlist entries to get recommendations.</p> : null}
      </section>

      <section className="content-band">
        <div className="section-header"><h2>Movie library</h2><span>{movies.data?.length ?? 0} films</span></div>
        <label className="movie-search"><Search size={16} /><input aria-label="Search movies" placeholder="Search your movie library" value={query} onChange={(event) => setQuery(event.target.value)} /></label>
        <form className="movie-add-form" onSubmit={submitMovie}>
          <input aria-label="Movie title" placeholder="Movie title" value={title} onChange={(event) => setTitle(event.target.value)} />
          <input aria-label="Release year" placeholder="Year" type="number" value={year} onChange={(event) => setYear(event.target.value)} />
          <input aria-label="Runtime" placeholder="Minutes" type="number" value={runtime} onChange={(event) => setRuntime(event.target.value)} />
          <input aria-label="Genres" placeholder="Genres, comma separated" value={genres} onChange={(event) => setGenres(event.target.value)} />
          <button className="icon-button" type="submit" title="Add movie" aria-label="Add movie"><Plus size={18} /></button>
        </form>
        <div className="movie-library">{(movies.data ?? []).map((movie) => <article className="movie-library-row" key={movie.id}><Poster title={movie.title} src={movie.poster_url} /><div><strong>{movie.title}</strong><small>{[movie.release_year, movie.runtime_minutes ? `${movie.runtime_minutes} min` : null].filter(Boolean).join(" · ") || "Details pending"}</small></div><button className="secondary-button" onClick={() => addWatchlist.mutate(movie.id)}><Plus size={15} /> Watchlist</button></article>)}</div>
      </section>
    </> : null}

    {view === "watchlist" ? <section className="content-band"><div className="section-header"><h2>Watchlist</h2><span>{watchlist.data?.length ?? 0} waiting</span></div><div className="movie-library">{(watchlist.data ?? []).map((item) => <article className="movie-library-row" key={item.id}><Poster title={item.movie.title} src={item.movie.poster_url} /><div><strong>{item.movie.title}</strong><small>{item.movie.runtime_minutes ? `${item.movie.runtime_minutes} min` : "Runtime pending"} · priority {item.priority}</small></div><div className="row-actions"><button className="icon-button" title="Mark watched" aria-label={`Mark ${item.movie.title} watched`} onClick={() => watched.mutate(item.movie_id)}><Check size={17} /></button><button className="icon-button" title="Remove" aria-label={`Remove ${item.movie.title}`} onClick={() => removeWatchlist.mutate(item.id)}><Archive size={17} /></button></div></article>)}</div>{!watchlist.isLoading && !watchlist.data?.length ? <p className="status-text">Your watchlist is clear.</p> : null}</section> : null}

    {view === "history" ? <section className="content-band"><div className="section-header"><h2>Watch history</h2><span>{history.data?.length ?? 0} viewings</span></div><div className="movie-history-list">{(history.data ?? []).map((item) => <article className="history-row" key={item.id}><span className="history-date">{formatDate(item.watched_at)}</span><div><strong>{item.movie.title}</strong><small>{item.rewatch ? "Rewatch" : "First watch"}{item.rating != null ? ` · ${item.rating}/${item.rating_scale}` : ""}</small></div></article>)}</div></section> : null}

    {view === "import" ? <section className="content-band import-panel">
      <div className="section-header"><h2>Letterboxd export</h2><span>Preview before saving</span></div>
      <div className="import-controls"><label>File type<select aria-label="Letterboxd file type" value={importKind} onChange={(event) => setImportKind(event.target.value)}><option value="DIARY">Diary</option><option value="WATCHLIST">Watchlist</option><option value="WATCHED">Watched</option><option value="RATINGS">Ratings</option></select></label><label className="file-button"><Upload size={16} /> Choose CSV<input aria-label="Choose Letterboxd CSV" type="file" accept=".csv,text/csv" onChange={(event) => void readImport(event.target.files?.[0])} /></label></div>
      {previewImport.isPending ? <p className="status-text">Reading export…</p> : null}
      {importBatch ? <><div className="import-summary"><span>{importBatch.summary.total ?? importBatch.rows.length} rows</span><span>{importBatch.summary.ready ?? 0} ready</span><span>{importBatch.summary.review_required ?? 0} need review</span></div><div className="import-rows">{importBatch.rows.map((row) => <article className="import-row" key={row.id}><div><strong>{row.normalized.title ?? "Untitled"}</strong><small>{row.normalized.year ?? "Year unknown"} · {row.status.replaceAll("_", " ")}</small>{row.error ? <p>{row.error}</p> : null}</div>{row.status === "REVIEW_REQUIRED" ? <div className="import-resolution"><select aria-label={`Resolve ${row.normalized.title}`} value={resolutionMovie[row.id] ?? ""} onChange={(event) => setResolutionMovie((current) => ({ ...current, [row.id]: event.target.value }))}><option value="">Choose matching movie</option>{(movies.data ?? []).map((movie) => <option key={movie.id} value={movie.id}>{movie.title} {movie.release_year ? `(${movie.release_year})` : ""}</option>)}</select><button className="icon-button" title="Confirm match" aria-label={`Confirm ${row.normalized.title} match`} disabled={!resolutionMovie[row.id]} onClick={() => resolveImport.mutate({ rowId: row.id, movieId: resolutionMovie[row.id] })}><Check size={16} /></button></div> : null}</article>)}</div><button className="primary-button import-confirm" disabled={!importBatch.rows.some((row) => row.status === "READY") || confirmImport.isPending} onClick={() => confirmImport.mutate(importBatch.id)}><Check size={16} /> Confirm ready rows</button></> : null}
    </section> : null}
  </div>;
}


function Poster({ src, title }: { src?: string | null; title: string }) {
  return src ? <img className="movie-poster" src={src} alt="" /> : <div className="movie-poster movie-poster-empty" aria-hidden="true"><Film size={19} /><span>{title.slice(0, 1)}</span></div>;
}


function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(new Date(value));
}
