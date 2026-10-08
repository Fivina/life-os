import { Check, Upload } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../../services/api";
import type { MovieImportBatch } from "../../types/api";

const sourceKindLabels: Record<string, string> = {
  DIARY: "Diary",
  WATCHLIST: "Watchlist",
  WATCHED: "Watched",
  RATINGS: "Ratings"
};

export function LetterboxdImportPanel({ active = true, showSettingsLink = false }: { active?: boolean; showSettingsLink?: boolean }) {
  const queryClient = useQueryClient();
  const [importBatch, setImportBatch] = useState<MovieImportBatch | null>(null);
  const [importKind, setImportKind] = useState("AUTO");
  const [resolutionMovie, setResolutionMovie] = useState<Record<string, string>>({});
  const movies = useQuery({ queryKey: ["movies", ""], queryFn: () => api.movies(""), enabled: active });

  const previewImport = useMutation({
    mutationFn: (payload: { file_name: string; content: string; source_kind?: string }) => api.previewLetterboxdImport(payload),
    onSuccess: (batch) => {
      setImportBatch(batch);
      setResolutionMovie({});
    }
  });
  const confirmImport = useMutation({
    mutationFn: (batchId: string) => api.confirmMovieImport(batchId),
    onSuccess: (batch) => {
      setImportBatch(batch);
      void queryClient.invalidateQueries({ queryKey: ["movies"] });
      void queryClient.invalidateQueries({ queryKey: ["movie-watchlist"] });
      void queryClient.invalidateQueries({ queryKey: ["movie-history"] });
      void queryClient.invalidateQueries({ queryKey: ["leisure-trajectory"] });
    }
  });
  const resolveImport = useMutation({
    mutationFn: ({ rowId, movieId }: { rowId: string; movieId: string }) => api.resolveMovieImportRow(rowId, movieId),
    onSuccess: (_, variables) => setImportBatch((current) => current ? {
      ...current,
      rows: current.rows.map((row) => row.id === variables.rowId
        ? { ...row, status: "READY", error: null, movie_id: variables.movieId }
        : row)
    } : current)
  });

  async function readImport(file?: File) {
    if (!file) return;
    previewImport.mutate({
      file_name: file.name,
      content: await file.text(),
      ...(importKind === "AUTO" ? {} : { source_kind: importKind })
    });
  }

  const previewDestinations = importBatch
    ? [...new Set(importBatch.rows.map((row) => sourceKindLabels[row.source_kind] ?? row.source_kind))]
    : [];
  const destinationLabel = importBatch
    ? `Preview destination${previewDestinations.length === 1 ? "" : "s"}: ${previewDestinations.join(", ") || "No importable rows"}`
    : importKind === "AUTO"
      ? "Destination: detect from filename"
      : `Selected destination: ${sourceKindLabels[importKind] ?? importKind}`;

  return <section className="content-band import-panel letterboxd-import-panel" aria-labelledby="letterboxd-import-heading" hidden={!active}>
    <div className="section-header">
      <div><h2 id="letterboxd-import-heading">Import from Letterboxd</h2><p>Choose an official CSV export, review every match, then confirm the ready rows.</p>{showSettingsLink ? <Link className="secondary-button" to="/settings/integrations/letterboxd">Open Letterboxd settings</Link> : null}</div>
      <span>Preview before saving</span>
    </div>
    <div className="import-controls">
      <label>File type<select aria-label="Letterboxd file type" value={importKind} onChange={(event) => setImportKind(event.target.value)}><option value="AUTO">Detect automatically</option><option value="DIARY">Diary</option><option value="WATCHLIST">Watchlist</option><option value="WATCHED">Watched</option><option value="RATINGS">Ratings</option></select></label>
      <label className="file-button"><Upload size={16} /> Choose CSV<input aria-label="Choose Letterboxd CSV" type="file" accept=".csv,text/csv" onChange={(event) => void readImport(event.target.files?.[0])} /></label>
    </div>
    <p className="status-text" role="status">{destinationLabel}</p>
    {previewImport.isPending ? <p className="status-text">Reading export…</p> : null}
    {previewImport.isError ? <p className="status-text error" role="alert">The Letterboxd CSV could not be previewed.</p> : null}
    {importBatch ? <>
      <div className="import-summary"><span>{importBatch.summary.total ?? importBatch.rows.length} rows</span><span>{importBatch.summary.ready ?? 0} ready</span><span>{importBatch.summary.review_required ?? 0} need review</span></div>
      <div className="import-rows">{importBatch.rows.map((row) => <article className="import-row" key={row.id}><div><strong>{row.normalized.title ?? "Untitled"}</strong><small>{row.normalized.year ?? "Year unknown"} · {row.status.replaceAll("_", " ")}</small>{row.error ? <p>This row could not be prepared for import.</p> : null}</div>{row.status === "REVIEW_REQUIRED" ? <div className="import-resolution"><select aria-label={`Resolve ${row.normalized.title}`} value={resolutionMovie[row.id] ?? ""} onChange={(event) => setResolutionMovie((current) => ({ ...current, [row.id]: event.target.value }))}><option value="">Choose matching movie</option>{(movies.data ?? []).map((movie) => <option key={movie.id} value={movie.id}>{movie.title} {movie.release_year ? `(${movie.release_year})` : ""}</option>)}</select><button className="icon-button" type="button" title="Confirm match" aria-label={`Confirm ${row.normalized.title} match`} disabled={!resolutionMovie[row.id] || resolveImport.isPending} onClick={() => resolveImport.mutate({ rowId: row.id, movieId: resolutionMovie[row.id] })}><Check size={16} /></button></div> : null}</article>)}</div>
      <button className="primary-button import-confirm" type="button" disabled={!importBatch.rows.some((row) => row.status === "READY") || confirmImport.isPending} onClick={() => confirmImport.mutate(importBatch.id)}><Check size={16} /> Confirm ready rows</button>
      {confirmImport.isError || resolveImport.isError ? <p className="status-text error" role="alert">The import could not be updated. Your preview is still available.</p> : null}
    </> : null}
  </section>;
}
