import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import type { PropsWithChildren } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { KitchenPage } from "../features/kitchen/KitchenPage";
import { api } from "../services/api";

vi.mock("../services/api", () => ({
  api: {
    kitchenStatus: vi.fn(),
    inventory: vi.fn(),
    addInventoryItem: vi.fn(),
    mutateInventory: vi.fn(),
    configureInventoryStaple: vi.fn(),
    kitchenRecipes: vi.fn(),
    createKitchenRecipe: vi.fn(),
    kitchenRecommendations: vi.fn(),
    mealPlans: vi.fn(),
    shoppingList: vi.fn(),
    recommendMealFromText: vi.fn(),
    startCookingSession: vi.fn(),
    updateCookingSession: vi.fn(),
    completeKitchenRecipe: vi.fn(),
    rejectMealRecommendation: vi.fn(),
    logManualMeal: vi.fn(),
    upsertNutritionTarget: vi.fn(),
    shoppingNeeds: vi.fn(),
    createShoppingForecast: vi.fn(),
    syncKitchenShoppingActions: vi.fn()
  }
}));

const mockedApi = vi.mocked(api);

function renderKitchen() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false }
    }
  });

  function Wrapper({ children }: PropsWithChildren) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  }

  return render(<KitchenPage />, { wrapper: Wrapper });
}

function statusFixture() {
  return {
    inventory_count: 1,
    expiring_lots: 1,
    expired_lots: 0,
    nutrition: {
      date: "2026-09-15",
      calories_target: 2400,
      protein_g_target: 170,
      calories_consumed: 700,
      protein_g_consumed: 52,
      calories_remaining: 1700,
      protein_g_remaining: 118,
      calories_over_target: 0,
      protein_g_over_target: 0
    },
    top_recommendation: null,
    shopping_need_count: 1,
    active_candidate_count: 0
  };
}

function recommendationFixture() {
  return {
    recommendation_id: "recommendation-1",
    option_id: "option-1",
    recipe: {
      id: "recipe-1",
      name: "Yogurt bowl",
      description: null,
      preparation_minutes: 8,
      cooking_minutes: 0,
      servings: 1,
      calories_per_serving: 320,
      protein_g_per_serving: 35,
      carbs_g_per_serving: null,
      fat_g_per_serving: null,
      protein_family: "dairy",
      difficulty: "easy",
      tags: ["dairy"],
      active: true,
      notes: null,
      ingredients: [],
      version: 1
    },
    score: 62,
    score_factors: {
      inventory_fit: 25,
      nutrition_fit: 28,
      ingredient_expiry_value: 5,
      preference_fit: 0,
      craving_context_fit: 0,
      cooking_skill_progress: 0,
      variety_value: 5,
      repeat_penalty: 0,
      shopping_friction: 0,
      time_cost: -1,
      waste_risk: 0
    },
    explanation: [],
    availability: "available",
    missing_ingredients: [],
    expiring_ingredients_used: ["Greek yogurt"]
  };
}

describe("KitchenPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedApi.kitchenStatus.mockResolvedValue(statusFixture());
    mockedApi.inventory.mockResolvedValue([
      {
        id: "item-1",
        ingredient_name: "Greek yogurt",
        quantity: 2,
        unit: "count",
        expires_on: "2026-09-16",
        source: "manual",
        category: null,
        canonical_unit: "count",
        default_storage_location: null,
        is_staple: false,
        restock_threshold: null,
        restock_target: null,
        active: true,
        notes: null,
        total_quantity: 2,
        expiry_status: "expires_soon",
        lots: [],
        version: 1
      }
    ]);
    mockedApi.kitchenRecipes.mockResolvedValue([]);
    mockedApi.kitchenRecommendations.mockResolvedValue([recommendationFixture()]);
    mockedApi.mealPlans.mockResolvedValue([]);
    mockedApi.shoppingList.mockResolvedValue([]);
    mockedApi.recommendMealFromText.mockResolvedValue({
      intent: { version: "meal-intent-v1", meal_type: null, cuisine_preferences: [], styles: [], protein_preferences: [], ingredient_preferences: [], ingredient_exclusions: [], dietary_constraints: [], max_total_minutes: 25, max_active_minutes: null, servings: 1, protein_priority: "HIGH", heaviness_preference: "LIGHT_TO_MEDIUM", inventory_preference: "SHOPPING_ALLOWED", confidence: 0.9, ambiguities: [], free_text_source: "high protein" },
      interpretation_mode: "AI",
      recommendation_id: "natural-1",
      response_text: "I found 1 meal option that fits the constraints.",
      options: [{ ...recommendationFixture(), reason_codes: ["protein_target_fit"], why_it_fits: "Yogurt bowl takes 8 minutes; inventory is fully in stock; it provides 35 g protein.", total_minutes: 8, active_minutes: 8, nutrition: { calories: 320, protein_g: 35, source: "canonical_recipe_snapshot" }, nutrition_confidence: "PARTIAL", inventory_status: "FULLY_IN_STOCK", ingredient_requirements: [], estimated_grocery_delta: null, grocery_currency: null, budget_status: "UNKNOWN", technique_opportunities: [] }]
    });
    mockedApi.shoppingNeeds.mockResolvedValue([
      {
        id: "need-1",
        title: "Shop for Chicken rice bowl",
        status: "active",
        required_by: "2026-09-18T10:00:00Z",
        reason: "Missing ingredients",
        source: "forecast",
        forecast_window_days: 3,
        metadata_json: {},
        items: [{ id: "need-item-1", shopping_need_id: "need-1", inventory_item_id: null, ingredient_name: "Chicken", quantity: 200, unit: "g", satisfied: false, version: 1 }],
        version: 1
      }
    ]);
    mockedApi.addInventoryItem.mockResolvedValue({} as never);
    mockedApi.mutateInventory.mockResolvedValue({} as never);
    mockedApi.configureInventoryStaple.mockResolvedValue({} as never);
    mockedApi.upsertNutritionTarget.mockResolvedValue({} as never);
    mockedApi.logManualMeal.mockResolvedValue({} as never);
    mockedApi.createKitchenRecipe.mockResolvedValue({} as never);
    mockedApi.completeKitchenRecipe.mockResolvedValue({} as never);
    mockedApi.rejectMealRecommendation.mockResolvedValue({} as never);
    mockedApi.createShoppingForecast.mockResolvedValue([]);
    mockedApi.syncKitchenShoppingActions.mockResolvedValue([]);
  });

  it("renders nutrition, inventory, recommendations, and shopping needs", async () => {
    renderKitchen();

    expect((await screen.findAllByText("Yogurt bowl")).length).toBeGreaterThan(0);
    expect(screen.getAllByText("Greek yogurt").length).toBeGreaterThan(0);
    expect(screen.getByText("Shop for Chicken rice bowl")).toBeInTheDocument();
    expect(within(screen.getByRole("region", { name: "Nutrition status" })).getByText("700")).toBeInTheDocument();
    expect(within(screen.getByRole("region", { name: "Nutrition status" })).getByText("52 / 170 g")).toBeInTheDocument();
  });

  it("uses a real planned meal in the hero and opens the existing receipt control", async () => {
    const now = new Date();
    const plannedFor = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 19).toISOString();
    mockedApi.mealPlans.mockResolvedValue([{ id: "plan-1", status: "planned", planned_for: plannedFor, recipe: { ...recommendationFixture().recipe, name: "Planned chickpea bowl" } } as never]);
    renderKitchen();

    const hero = await screen.findByRole("region", { name: "Relevant meal" });
    expect(await within(hero).findByText("Planned chickpea bowl")).toBeInTheDocument();
    expect(within(hero).getByRole("heading", { name: "Planned for today" })).toBeInTheDocument();
    const receiptSection = document.getElementById("receipt-inbox")!;
    receiptSection.scrollIntoView = vi.fn();
    fireEvent.click(screen.getByRole("button", { name: "Scan receipt" }));
    expect(receiptSection.scrollIntoView).toHaveBeenCalled();
  });

  it("shows unavailable states when Kitchen data cannot be loaded", async () => {
    const failure = new Error("Kitchen offline");
    mockedApi.kitchenStatus.mockRejectedValue(failure);
    mockedApi.inventory.mockRejectedValue(failure);
    mockedApi.kitchenRecommendations.mockRejectedValue(failure);
    mockedApi.mealPlans.mockRejectedValue(failure);
    mockedApi.shoppingList.mockRejectedValue(failure);
    mockedApi.shoppingNeeds.mockRejectedValue(failure);
    renderKitchen();

    expect(await screen.findByText("Inventory unavailable")).toBeInTheDocument();
    expect(screen.getByText("Meals unavailable")).toBeInTheDocument();
    expect(screen.getByText("Shopping list unavailable.")).toBeInTheDocument();
    expect(screen.queryByText("0 ingredients recorded")).not.toBeInTheDocument();
  });

  it("turns a natural meal request into structured Chef cards", async () => {
    renderKitchen();
    const input = screen.getByLabelText(/what would you like/i);
    fireEvent.change(input, { target: { value: "High protein, not too heavy, 25 minutes" } });
    fireEvent.click(screen.getByRole("button", { name: /recommend/i }));
    await waitFor(() => expect(mockedApi.recommendMealFromText).toHaveBeenCalledWith({ request: "High protein, not too heavy, 25 minutes", limit: 5 }));
    expect(await screen.findByText("Chef's Shortlist")).toBeInTheDocument();
    expect(screen.getAllByText(/35 ?g protein/i).length).toBeGreaterThan(0);
  });

  it("adds inventory with bounded units and expiry", async () => {
    renderKitchen();

    await screen.findAllByText("Yogurt bowl");
    fireEvent.change(screen.getAllByLabelText(/ingredient/i)[0], { target: { value: "Oats" } });
    fireEvent.change(screen.getByLabelText(/^quantity$/i), { target: { value: "300" } });
    fireEvent.change(screen.getByLabelText(/^unit$/i), { target: { value: "g" } });
    fireEvent.click(screen.getByRole("button", { name: /^add$/i }));

    await waitFor(() => expect(mockedApi.addInventoryItem).toHaveBeenCalled());
    expect(mockedApi.addInventoryItem.mock.calls[0][0]).toMatchObject({ ingredient_name: "Oats", quantity: 300, unit: "g" });
  });

  it("logs a manual meal and completes an available recommendation with feedback", async () => {
    renderKitchen();

    fireEvent.click(await screen.findByRole("button", { name: /^log$/i }));
    await waitFor(() => expect(mockedApi.logManualMeal).toHaveBeenCalled());

    fireEvent.click(within(screen.getByRole("region", { name: "Relevant meal" })).getByRole("button", { name: /^cook$/i }));
    expect(await screen.findByRole("region", { name: /cooking mode/i })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText(/feedback/i), { target: { value: "Smooth and filling" } });
    fireEvent.click(screen.getByRole("button", { name: /mark cooked/i }));
    await waitFor(() => expect(mockedApi.completeKitchenRecipe).toHaveBeenCalledWith("recipe-1", { servings: 1, satisfaction: 4, notes: "Smooth and filling" }));
  });

  it("creates recipes, forecasts shopping, and syncs candidate actions", async () => {
    renderKitchen();

    fireEvent.click(await screen.findByRole("button", { name: /create recipe/i }));
    await waitFor(() => expect(mockedApi.createKitchenRecipe).toHaveBeenCalled());
    expect(mockedApi.createKitchenRecipe.mock.calls[0][0].ingredients[0]).toMatchObject({ ingredient_name: "Greek yogurt" });

    fireEvent.click(screen.getByRole("button", { name: /forecast 3 days/i }));
    await waitFor(() => expect(mockedApi.createShoppingForecast).toHaveBeenCalled());
    fireEvent.click(screen.getByRole("button", { name: /sync actions/i }));
    await waitFor(() => expect(mockedApi.syncKitchenShoppingActions).toHaveBeenCalled());
  });

  it("updates fridge quantities and records rejected recommendations", async () => {
    renderKitchen();

    await screen.findAllByText("Yogurt bowl");
    fireEvent.change(screen.getByLabelText(/^use$/i), { target: { value: "0.5" } });
    fireEvent.click(screen.getByTitle(/consume amount/i));
    await waitFor(() => expect(mockedApi.mutateInventory).toHaveBeenCalledWith("item-1", { operation: "consume", quantity: 0.5, unit: "count", reason: "Manual consumption" }));

    fireEvent.click(screen.getByTitle(/reject recommendation/i));
    await waitFor(() => expect(mockedApi.rejectMealRecommendation).toHaveBeenCalledWith("recommendation-1", "option-1", "Not for me right now"));
  });
});
