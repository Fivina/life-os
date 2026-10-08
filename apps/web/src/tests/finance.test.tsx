import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { PropsWithChildren } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { FinancePage } from "../features/finance/FinancePage";
import { api } from "../services/api";

vi.mock("../services/api", () => ({
  api: {
    financeOverview: vi.fn(),
    createFinanceImport: vi.fn(),
    updateFinanceImportRow: vi.fn(),
    confirmFinanceImport: vi.fn(),
    saveFinanceBudget: vi.fn(),
    refreshRecurringExpenses: vi.fn()
  }
}));

const mockedApi = vi.mocked(api);

function renderFinance() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  function Wrapper({ children }: PropsWithChildren) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  }
  return render(<FinancePage />, { wrapper: Wrapper });
}

const overview = {
  month_start: "2026-09-01", currency: "EUR", income: "2000.00", spending: "320.00", category_totals: { Groceries: "120.00" },
  budgets: [{ id: "budget-1", name: "Groceries", category_name: "Groceries", amount: "400.00", spent: "120.00", remaining: "280.00", currency: "EUR", month_start: "2026-09-01", protected: true, active: true, version: 1 }],
  recurring_expenses: [{ id: "rec-1", name: "Spotify", typical_amount: "10.99", currency: "EUR", interval_days: 30, next_expected_on: "2026-10-01", confidence: 0.85, evidence_count: 3, status: "likely", version: 1 }],
  safe_to_spend: { currency: "EUR", income_to_date: "2000.00", spending_to_date: "320.00", upcoming_recurring: "10.99", protected_budget_remaining: "280.00", planned_savings: "0.00", safe_to_spend: "1389.01", assumptions: ["Uses recorded transactions."] },
  recent_transactions: [{ id: "tx-1", occurred_on: "2026-09-12", amount: "42.00", currency: "EUR", direction: "expense", merchant_name: "Rewe", category_name: "Groceries", source: "csv", version: 1 }],
  savings_goals: []
};

describe("FinancePage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedApi.financeOverview.mockResolvedValue(overview);
    mockedApi.saveFinanceBudget.mockResolvedValue(overview.budgets[0]);
    mockedApi.refreshRecurringExpenses.mockResolvedValue([] as never);
  });

  it("renders bounded finance state and assumptions", async () => {
    renderFinance();
    expect(await screen.findByText("Spotify")).toBeInTheDocument();
    expect(screen.getByText("Rewe")).toBeInTheDocument();
    expect(screen.getByText("Uses recorded transactions.")).toBeInTheDocument();
    expect(screen.getByText((content) => content.includes("1,389") || content.includes("1.389"))).toBeInTheDocument();
  });

  it("saves a protected grocery budget", async () => {
    renderFinance();
    await screen.findByText("Spotify");
    fireEvent.change(screen.getByLabelText(/^amount$/i), { target: { value: "450" } });
    fireEvent.click(screen.getByLabelText(/protect this amount/i));
    fireEvent.click(screen.getByRole("button", { name: /save budget/i }));
    await waitFor(() => expect(mockedApi.saveFinanceBudget).toHaveBeenCalled());
    expect(mockedApi.saveFinanceBudget.mock.calls[0][0]).toMatchObject({ name: "Groceries", category: "Groceries", amount: 450, protected: true });
  });
});
