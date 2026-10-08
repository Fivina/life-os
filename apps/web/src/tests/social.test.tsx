import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SocialPage } from "../features/social/SocialPage";
import { api } from "../services/api";

vi.mock("../services/api", () => ({ api: {
  socialTrajectory: vi.fn(), updateSocialTrajectory: vi.fn(), socialActivities: vi.fn(), addSocialActivity: vi.fn(),
  opportunities: vi.fn(), recommendOpportunities: vi.fn(), dismissOpportunity: vi.fn(), recordOpportunityOutcome: vi.fn(),
  opportunitySources: vi.fn(), updateOpportunitySource: vi.fn(), discoverOpportunities: vi.fn()
} }));

const mockedApi = vi.mocked(api);

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}><SocialPage /></QueryClientProvider>);
}

describe("v1.8C social opportunities", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedApi.socialTrajectory.mockResolvedValue({ goal_id: "g1", trajectory_id: "t1", enabled: true, period: "WEEK", target_min: 2, target_max: 3, week_starts_on: 0, period_start: "2026-09-21T00:00:00Z", period_end: "2026-09-28T00:00:00Z", completed_count: 1, state: "BELOW_RANGE", remaining_to_min: 1, qualification: "explicit activity" });
    mockedApi.socialActivities.mockResolvedValue([]);
    mockedApi.opportunities.mockResolvedValue([{ id: "e1", opportunity_type: "CONCERT", title: "Aurora", starts_at: "2026-10-03T18:00:00Z", timezone: "Europe/Berlin", venue: "Tempodrom", city: "Berlin", status: "ACTIVE", tags: ["music"], user_status: "AVAILABLE", reasons: ["Matches an explicit future interest"], feasibility: { feasible: true, status: "CLEAN_SLOT" } }]);
    mockedApi.opportunitySources.mockResolvedValue([{ id: "s1", source_id: "ticketmaster", enabled: false, configured: false, city: "Berlin", country_code: "DE", categories: [], cadence_minutes: 360, horizon_days: 30, last_status: "NEVER", last_summary: {} }]);
  });

  it("uses neutral weekly language and shows only contextual opportunity detail", async () => {
    renderPage();
    expect(await screen.findByText(/1 this week · target 2–3/i)).toBeInTheDocument();
    expect(await screen.findByText("Aurora")).toBeInTheDocument();
    expect(screen.getByText("Calendar clear")).toBeInTheDocument();
    expect(screen.queryByText(/deficit|failed|isolated/i)).not.toBeInTheDocument();
  });

  it("keeps interested separate from attended", async () => {
    mockedApi.recommendOpportunities.mockResolvedValue({ id: "r1", domain: "social", kind: "opportunity", title: "Relevant opportunities", options: [{ id: "o1", label: "Aurora", rank: 1, reference_id: "e1", payload_json: { opportunity_id: "e1", reasons: ["Matches an explicit future interest"], feasibility: { status: "CLEAN_SLOT" } } }] });
    mockedApi.recordOpportunityOutcome.mockResolvedValue({});
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: /refresh picks/i }));
    expect((await screen.findAllByText("Aurora")).length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole("button", { name: "Interested in Aurora" }));
    await waitFor(() => expect(mockedApi.recordOpportunityOutcome).toHaveBeenCalledWith(expect.objectContaining({ outcome: "SELECTED" })));
    expect(mockedApi.addSocialActivity).not.toHaveBeenCalled();
  });
});
