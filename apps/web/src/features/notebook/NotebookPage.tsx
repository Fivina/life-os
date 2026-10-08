import { Archive, Check, Lightbulb, Search, Upload } from "lucide-react";
import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../../services/api";


export function NotebookPage() {
  const queryClient = useQueryClient();
  const [entryType, setEntryType] = useState<"GENERAL" | "IMPLEMENTATION_IDEA">("IMPLEMENTATION_IDEA");
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [search, setSearch] = useState("");
  const entries = useQuery({ queryKey: ["notebook_entries"], queryFn: () => api.notebookEntries() });
  const searchResults = useQuery({ queryKey: ["notebook-search", search], queryFn: () => api.searchNotebook(search), enabled: search.trim().length > 0 });
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["notebook_entries"] });
  const create = useMutation({ mutationFn: api.createNotebookEntry, onSuccess: () => { setTitle(""); setContent(""); refresh(); } });
  const review = useMutation({ mutationFn: api.reviewNotebookEntry, onSuccess: refresh });
  const archive = useMutation({ mutationFn: api.archiveNotebookEntry, onSuccess: refresh });
  const promote = useMutation({ mutationFn: api.promoteNotebookEntry, onSuccess: refresh });
  const visible = search.trim() ? (searchResults.data ?? []).map((item) => item.entry) : (entries.data ?? []);

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!title.trim() || !content.trim()) return;
    create.mutate({ entry_type: entryType, title: title.trim(), content: content.trim() });
  }

  return <div className="stack notebook-page">
    <section className="content-band">
      <div className="section-header"><h2>Notebook</h2><span>{entries.data?.length ?? 0} entries</span></div>
      <form className="notebook-capture" onSubmit={submit}>
        <div className="segmented-control" aria-label="Entry type">
          <button type="button" className={entryType === "IMPLEMENTATION_IDEA" ? "active" : ""} onClick={() => setEntryType("IMPLEMENTATION_IDEA")}><Lightbulb size={15} /> Idea</button>
          <button type="button" className={entryType === "GENERAL" ? "active" : ""} onClick={() => setEntryType("GENERAL")}>Note</button>
        </div>
        <input aria-label="Title" placeholder="Title" value={title} onChange={(event) => setTitle(event.target.value)} />
        <textarea aria-label="Content" placeholder="Write it down without turning it into a task." value={content} onChange={(event) => setContent(event.target.value)} rows={4} />
        <button className="primary-button" type="submit" disabled={create.isPending}>Save entry</button>
      </form>
    </section>
    <section className="content-band">
      <label className="notebook-search"><Search size={16} /><input aria-label="Search notebook" placeholder="Search ideas and notes" value={search} onChange={(event) => setSearch(event.target.value)} /></label>
      <div className="notebook-list">
        {visible.map((entry) => <article className="notebook-row" key={entry.id}>
          <div><small>{entry.entry_type.replaceAll("_", " ")} · {entry.status}</small><strong>{entry.title}</strong><p>{entry.content}</p></div>
          <div className="notebook-actions">
            {entry.status === "ACTIVE" ? <button className="icon-button" title="Mark reviewed" aria-label={`Review ${entry.title}`} onClick={() => review.mutate(entry.id)}><Check size={16} /></button> : null}
            {entry.status !== "PROMOTED" ? <button className="icon-button" title="Promote to manual development review" aria-label={`Promote ${entry.title}`} onClick={() => promote.mutate(entry.id)}><Upload size={16} /></button> : null}
            {entry.status !== "ARCHIVED" ? <button className="icon-button" title="Archive" aria-label={`Archive ${entry.title}`} onClick={() => archive.mutate(entry.id)}><Archive size={16} /></button> : null}
          </div>
        </article>)}
        {!entries.isLoading && visible.length === 0 ? <p className="status-text">No matching notebook entries.</p> : null}
      </div>
    </section>
  </div>;
}
