import { Check, FileText, PiggyBank, RefreshCw, Upload, WalletCards } from "lucide-react";
import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { StatTile } from "../../components/StatTile";
import { api } from "../../services/api";
import type { FinanceImportBatch } from "../../types/api";

function money(value?: string | number | null, currency = "EUR") {
  return new Intl.NumberFormat(undefined, { style: "currency", currency }).format(Number(value ?? 0));
}

export function FinancePage() {
  const queryClient = useQueryClient();
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [batch, setBatch] = useState<FinanceImportBatch | null>(null);
  const [budgetName, setBudgetName] = useState("Groceries");
  const [budgetCategory, setBudgetCategory] = useState("Groceries");
  const [budgetAmount, setBudgetAmount] = useState("400");
  const [protectedBudget, setProtectedBudget] = useState(false);
  const overview = useQuery({ queryKey: ["finance-overview"], queryFn: api.financeOverview });
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["finance-overview"] });
  const importCsv = useMutation({ mutationFn: async (file: File) => api.createFinanceImport({ filename: file.name, content: await file.text(), currency: "EUR" }), onSuccess: setBatch });
  const updateRow = useMutation({ mutationFn: ({ id, category, accept }: { id: string; category?: string; accept: boolean }) => api.updateFinanceImportRow(id, { category, accept }), onSuccess: setBatch });
  const confirmImport = useMutation({ mutationFn: api.confirmFinanceImport, onSuccess: (value) => { setBatch(value); refresh(); } });
  const saveBudget = useMutation({ mutationFn: api.saveFinanceBudget, onSuccess: refresh });
  const refreshRecurring = useMutation({ mutationFn: api.refreshRecurringExpenses, onSuccess: refresh });
  const data = overview.data;

  function submitBudget(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const now = new Date();
    saveBudget.mutate({ name: budgetName, category: budgetCategory || null, amount: Number(budgetAmount), currency: "EUR", month_start: `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-01`, protected: protectedBudget });
  }

  return <div className="stack">
    <section className="stat-grid">
      <StatTile label="Safe to spend" value={money(data?.safe_to_spend.safe_to_spend, data?.currency)} tone="green" />
      <StatTile label="Income" value={money(data?.income, data?.currency)} tone="blue" />
      <StatTile label="Spending" value={money(data?.spending, data?.currency)} tone="amber" />
      <StatTile label="Recurring" value={`${data?.recurring_expenses.length ?? 0}`} tone="rose" />
    </section>

    <section className="content-band kitchen-hero"><div><div className="section-header"><h2>Finance</h2><span>recorded data only</span></div><p className="status-text">Review imports before they become canonical. Life OS never moves money or invents account balances.</p></div><a className="primary-button" href="/self/assistant?q=Explain%20my%20safe-to-spend%20estimate"><WalletCards size={17} /><span>Ask Finance</span></a></section>

    <section className="split-grid">
      <article className="content-band"><div className="section-header"><h2>Safe To Spend</h2><PiggyBank size={18} /></div><div className="finance-breakdown"><span>Spent to date <strong>{money(data?.safe_to_spend.spending_to_date)}</strong></span><span>Upcoming recurring <strong>{money(data?.safe_to_spend.upcoming_recurring)}</strong></span><span>Protected budgets <strong>{money(data?.safe_to_spend.protected_budget_remaining)}</strong></span></div>{data?.safe_to_spend.assumptions.map((item) => <p className="status-text" key={item}>{item}</p>)}</article>
      <article className="content-band"><div className="section-header"><h2>Monthly Budget</h2><PiggyBank size={18} /></div><form className="compact-form" onSubmit={submitBudget}><label>Name<input value={budgetName} onChange={(event) => setBudgetName(event.target.value)} /></label><label>Category<input value={budgetCategory} onChange={(event) => setBudgetCategory(event.target.value)} /></label><label>Amount<input inputMode="decimal" value={budgetAmount} onChange={(event) => setBudgetAmount(event.target.value)} /></label><label className="toggle-line"><input type="checkbox" checked={protectedBudget} onChange={(event) => setProtectedBudget(event.target.checked)} />Protect this amount</label><button className="primary-button" disabled={saveBudget.isPending} type="submit"><Check size={17} />Save budget</button></form></article>
    </section>

    <section className="content-band"><div className="section-header"><h2>CSV Import</h2><FileText size={18} /></div><form className="compact-form" onSubmit={(event) => { event.preventDefault(); if (csvFile) importCsv.mutate(csvFile); }}><label>Bank export<input type="file" accept=".csv,text/csv" onChange={(event) => setCsvFile(event.target.files?.[0] ?? null)} /></label><button className="primary-button" disabled={!csvFile || importCsv.isPending} type="submit"><Upload size={17} />Stage import</button></form>
      {batch ? <div className="review-panel"><div className="section-header"><strong>{batch.filename}</strong><span>{batch.status.replaceAll("_", " ")} · {batch.ready_count} ready · {batch.review_count} review · {batch.error_count} errors</span></div><div className="kitchen-list">{batch.rows.map((row) => <form className="candidate-row" key={row.id} onSubmit={(event) => { event.preventDefault(); const form = new FormData(event.currentTarget); updateRow.mutate({ id: row.id, category: String(form.get("category") || "Other"), accept: true }); }}><div><strong>{row.merchant_raw || row.description || `Row ${row.row_number}`}</strong><small>{row.occurred_on ?? "No date"} · {row.direction ?? "unknown"} · {money(row.amount, row.currency)}</small>{row.error ? <small className="error">{row.error}</small> : null}</div>{row.review_required ? <div className="inline-review"><input aria-label="Category" name="category" defaultValue={row.category_name ?? "Other"} /><button className="secondary-button" type="submit">Accept</button><button className="secondary-button" type="button" onClick={() => updateRow.mutate({ id: row.id, accept: false })}>Dismiss</button></div> : <span>{row.status}</span>}</form>)}</div><button className="primary-button" type="button" disabled={batch.review_count > 0 || batch.error_count > 0 || confirmImport.isPending || batch.status === "confirmed"} onClick={() => confirmImport.mutate(batch.id)}><Check size={17} />Confirm import</button></div> : null}
    </section>

    <section className="split-grid">
      <article className="content-band"><div className="section-header"><h2>Budgets</h2><span>{data?.budgets.length ?? 0}</span></div><div className="kitchen-list">{data?.budgets.map((item) => <div className="candidate-row" key={item.id}><div><strong>{item.name}</strong><small>{item.category_name ?? "Overall"} · spent {money(item.spent, item.currency)}</small><div className="progress-line"><span style={{ width: `${Math.min(100, Number(item.spent) / Math.max(1, Number(item.amount)) * 100)}%` }} /></div></div><span>{money(item.remaining, item.currency)}</span></div>)}{!overview.isLoading && !data?.budgets.length ? <p className="empty-state-inline">No monthly budget yet. Add one above to make safe-to-spend more useful.</p> : null}</div></article>
      <article className="content-band"><div className="section-header"><h2>Recurring Expenses</h2><button className="secondary-button" title="Refresh recurring detection" type="button" onClick={() => refreshRecurring.mutate()}><RefreshCw size={16} /></button></div><div className="kitchen-list">{data?.recurring_expenses.map((item) => <div className="candidate-row" key={item.id}><div><strong>{item.name}</strong><small>About every {item.interval_days} days · {Math.round(item.confidence * 100)}% confidence</small></div><span>{money(item.typical_amount, item.currency)}</span></div>)}{!overview.isLoading && !data?.recurring_expenses.length ? <p className="empty-state-inline">No recurring pattern has enough evidence yet.</p> : null}</div></article>
    </section>

    <section className="content-band"><div className="section-header"><h2>Recent Transactions</h2><span>latest {data?.recent_transactions.length ?? 0}</span></div><div className="kitchen-list">{data?.recent_transactions.map((item) => <div className="candidate-row" key={item.id}><div><strong>{item.merchant_name || item.merchant_raw || item.description || "Transaction"}</strong><small>{item.occurred_on} · {item.category_name ?? "Uncategorized"} · {item.source}</small></div><span>{item.direction === "expense" ? "-" : "+"}{money(item.amount, item.currency)}</span></div>)}{!overview.isLoading && !data?.recent_transactions.length ? <p className="empty-state-inline">No transactions recorded. Stage a bank CSV above to begin.</p> : null}</div></section>
  </div>;
}
