import { BookOpen, ChefHat, Clock3, Plus, ReceiptText, Refrigerator, ShoppingCart, Sparkles, Target, Utensils } from "lucide-react";

import type { InventoryItem, KitchenStatus, MealPlan, MealRecommendation, NutritionProgress, Recipe, ShoppingAggregate, ShoppingNeed } from "../../types/api";

type KitchenOverviewProps = {
  status?: KitchenStatus;
  inventory: InventoryItem[];
  plans: MealPlan[];
  recommendation?: MealRecommendation;
  shopping: ShoppingAggregate[];
  shoppingNeeds: ShoppingNeed[];
  mealLoading: boolean;
  mealError: boolean;
  inventoryLoading: boolean;
  inventoryError: boolean;
  nutritionLoading: boolean;
  nutritionError: boolean;
  shoppingLoading: boolean;
  shoppingError: boolean;
  onCookPlan: (plan: MealPlan) => void;
  onCookRecipe: (recipe: Recipe) => void;
  onPlanRecommendation: (recommendation: MealRecommendation) => void;
  onOpen: (section: string) => void;
};

function dateKey(value: Date | string) {
  const date = typeof value === "string" ? new Date(value) : value;
  return `${date.getFullYear()}-${date.getMonth()}-${date.getDate()}`;
}

function weekDays(now: Date) {
  const monday = new Date(now.getFullYear(), now.getMonth(), now.getDate() - ((now.getDay() + 6) % 7));
  return Array.from({ length: 7 }, (_, index) => new Date(monday.getFullYear(), monday.getMonth(), monday.getDate() + index));
}

function inventoryState(item: InventoryItem) {
  if (item.expiry_status === "expired") return { label: "Expired", tone: "critical" };
  if (item.expiry_status === "expires_today") return { label: "Use today", tone: "soon" };
  if (item.expiry_status === "expires_soon") return { label: "Use soon", tone: "soon" };
  if (item.expires_on) return { label: new Date(item.expires_on).toLocaleDateString(undefined, { month: "short", day: "numeric" }), tone: "normal" };
  return { label: "No expiry", tone: "normal" };
}

function NutritionStatus({ nutrition, loading, error, onOpen }: { nutrition?: NutritionProgress; loading: boolean; error: boolean; onOpen: () => void }) {
  const calories = nutrition?.calories_consumed ?? 0;
  const target = nutrition?.calories_target;
  const protein = nutrition?.protein_g_consumed ?? 0;
  const proteinTarget = nutrition?.protein_g_target;
  const progress = target ? Math.min(100, Math.max(0, calories / target * 100)) : 0;
  return <section className="kitchen-panel kitchen-nutrition" aria-label="Nutrition status">
    <div className="kitchen-panel-head"><div><Target size={19} /><h2>Nutrition today</h2></div><button type="button" onClick={onOpen}>Targets <span aria-hidden="true">↗</span></button></div>
    {nutrition ? <div className="kitchen-nutrition-body">
      <div className="kitchen-nutrition-ring" style={{ "--kitchen-progress": `${progress}%` } as React.CSSProperties}><strong>{Math.round(calories).toLocaleString()}</strong><small>{target ? `/ ${Math.round(target).toLocaleString()} kcal` : "kcal logged"}</small></div>
      <div className="kitchen-nutrition-detail"><span>Protein</span><strong>{Math.round(protein)}{proteinTarget ? ` / ${Math.round(proteinTarget)}` : ""} g</strong><div className="kitchen-meter"><span style={{ width: `${proteinTarget ? Math.min(100, protein / proteinTarget * 100) : 0}%` }} /></div><small>{target ? "Based on meals recorded today" : "Set a target to track progress"}</small></div>
    </div> : <div className="kitchen-nutrition-empty"><span aria-hidden="true">—</span><div><strong>{loading ? "Loading today’s progress" : error ? "Progress unavailable" : "No nutrition data yet"}</strong><p>{loading ? "Checking logged meals and targets." : error ? "Open targets to review your settings." : "Log a meal or set a target to begin."}</p></div></div>}
  </section>;
}

export function KitchenOverview({ status, inventory, plans, recommendation, shopping, shoppingNeeds, mealLoading, mealError, inventoryLoading, inventoryError, nutritionLoading, nutritionError, shoppingLoading, shoppingError, onCookPlan, onCookRecipe, onPlanRecommendation, onOpen }: KitchenOverviewProps) {
  const today = new Date();
  const todayKey = dateKey(today);
  const activePlans = plans.filter((plan) => plan.status !== "completed" && plan.status !== "cancelled").sort((a, b) => new Date(a.planned_for).getTime() - new Date(b.planned_for).getTime());
  const tonight = activePlans.find((plan) => dateKey(plan.planned_for) === todayKey);
  const nextPlan = tonight ?? activePlans.find((plan) => new Date(plan.planned_for).getTime() >= today.getTime());
  const meal = nextPlan?.recipe ?? recommendation?.recipe;
  const mealLabel = tonight ? "Planned for today" : nextPlan ? "Next planned meal" : recommendation ? "Chef recommendation" : "Meal workspace";
  const visibleInventory = [...inventory].sort((a, b) => {
    const rank = (item: InventoryItem) => item.expiry_status === "expired" ? 0 : item.expiry_status === "expires_today" ? 1 : item.expiry_status === "expires_soon" ? 2 : 3;
    return rank(a) - rank(b) || a.ingredient_name.localeCompare(b.ingredient_name);
  }).slice(0, 5);
  const urgentCount = inventory.filter((item) => item.expiry_status === "expired" || item.expiry_status === "expires_today").length;
  const soonCount = inventory.filter((item) => item.expiry_status === "expires_soon").length;
  const activeShoppingNeeds = shoppingNeeds.filter((need) => need.status !== "completed" && need.status !== "cancelled");
  const shoppingCount = shopping.length || activeShoppingNeeds.reduce((count, need) => count + need.items.filter((item) => !item.satisfied).length, 0);
  const recommendedMinutes = recommendation ? recommendation.recipe.preparation_minutes + recommendation.recipe.cooking_minutes : 0;
  const suggestion = recommendation ? recommendation.expiring_ingredients_used.length
    ? `Use ${recommendation.expiring_ingredients_used.join(", ")} soon. ${recommendation.recipe.name} takes about ${recommendedMinutes} min.`
    : recommendation.missing_ingredients.length
      ? `${recommendation.recipe.name} needs ${recommendation.missing_ingredients.join(", ")}. Review it in Chef.`
      : `You have what you need for ${recommendation.recipe.name}. Ready in about ${recommendedMinutes} min.` : null;
  const mealDescription = meal?.description && !/\bscores?\s+\d|inventory availability/i.test(meal.description)
    ? meal.description : meal ? `${meal.ingredients.length} ingredients · ${meal.servings} serving${meal.servings === 1 ? "" : "s"}` : "";

  return <div className="kitchen-overview">
    <header className="kitchen-heading"><div className="kitchen-heading-icon"><ChefHat size={29} strokeWidth={1.6} /></div><div><span className="kitchen-eyebrow">HOME / KITCHEN</span><h1>Kitchen</h1><p>Plan the meal. Know what you have.</p></div><div className="kitchen-heading-date">{today.toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" })}<small>{status ? `${status.inventory_count} ${status.inventory_count === 1 ? "ingredient" : "ingredients"} in your fridge` : "Your food workspace"}</small></div></header>

    <section className="kitchen-suggestion" aria-label="PHÉNGOS suggestion"><span className="kitchen-suggestion-mark" aria-hidden="true" /><span className="kitchen-suggestion-label">PHÉNGOS SUGGESTION</span><p>{recommendation ? suggestion ?? `${recommendation.recipe.name} matches your current kitchen data.` : mealLoading ? "Checking your recipes and kitchen state…" : mealError ? "Meal suggestions are unavailable right now. Open Chef to try again." : "No meal suggestion yet. Add a recipe or ask Chef for a recommendation."}</p><button type="button" onClick={() => onOpen("chef-workspace")}>Open Chef <span aria-hidden="true">↗</span></button></section>

    <div className="kitchen-dashboard-grid">
      <section className="kitchen-panel kitchen-meal" aria-label="Relevant meal">
        <div className="kitchen-panel-head"><div><Utensils size={19} /><h2>{mealLabel}</h2></div>{meal ? <span className="kitchen-chip"><Clock3 size={14} /> {meal.preparation_minutes + meal.cooking_minutes} min</span> : null}</div>
        <div className="kitchen-meal-content"><div className="kitchen-meal-media" aria-hidden="true"><div className="kitchen-plate"><div className="kitchen-plate-inner"><Utensils size={35} strokeWidth={1.1} /></div></div><span className="kitchen-media-index">K / 01</span></div><div className="kitchen-meal-info">{meal ? <><span className="kitchen-eyebrow">{nextPlan ? new Date(nextPlan.planned_for).toLocaleDateString(undefined, { weekday: "long", month: "short", day: "numeric" }) : "Based on your current kitchen"}</span><h3>{meal.name}</h3><p>{mealDescription}</p><div className="kitchen-meal-facts"><span>{Math.round(meal.calories_per_serving)} kcal / serving</span><span>{Math.round(meal.protein_g_per_serving)} g protein</span>{recommendation ? <span>{recommendation.missing_ingredients.length ? `${recommendation.missing_ingredients.length} missing` : "Ingredients available"}</span> : null}</div></> : <><span className="kitchen-eyebrow">YOUR MEAL SPACE</span><h3>{mealLoading ? "Loading your meals…" : mealError ? "Meals unavailable" : "Make a meal plan"}</h3><p>{mealLoading ? "Checking your saved meals and recipes." : mealError ? "Your saved meals could not be loaded. Chef tools remain below." : "Ask Chef about your saved recipes, or create the first one below."}</p></>}</div></div>
        <div className="kitchen-meal-actions">{nextPlan ? <button className="kitchen-action-primary" type="button" onClick={() => onCookPlan(nextPlan)}><Utensils size={16} /> Open cooking</button> : recommendation && meal ? <button className="kitchen-action-primary" type="button" disabled={recommendation.availability !== "available"} onClick={() => onCookRecipe(meal)}><Utensils size={16} /> Cook</button> : <button className="kitchen-action-primary" type="button" onClick={() => onOpen("chef-workspace")}><ChefHat size={16} /> Ask Chef</button>}{!nextPlan && recommendation?.recommendation_id && recommendation.option_id ? <button type="button" onClick={() => onPlanRecommendation(recommendation)}>Plan meal</button> : null}<button type="button" onClick={() => onOpen(nextPlan ? "planned-meals" : "chef-workspace")}><BookOpen size={16} /> {nextPlan ? "Meal plans" : "View options"}</button></div>
      </section>

      <section className="kitchen-panel kitchen-fridge" aria-label="Fridge status"><div className="kitchen-panel-head"><div><Refrigerator size={19} /><h2>Fridge</h2></div><button type="button" onClick={() => onOpen("fridge-inventory")}>View all <span aria-hidden="true">↗</span></button></div><p className="kitchen-panel-caption">{inventoryLoading ? "Checking inventory" : inventoryError ? "Inventory unavailable" : urgentCount ? `${urgentCount} need attention` : soonCount ? `${soonCount} to use soon` : `${inventory.length} ingredients recorded`}</p><div className="kitchen-fridge-list">{visibleInventory.map((item) => { const state = inventoryState(item); return <div className="kitchen-fridge-item" key={item.id}><span className="kitchen-fridge-name">{item.ingredient_name}</span><span className="kitchen-fridge-amount">{item.total_quantity} {item.canonical_unit}</span><span className={`kitchen-expiry kitchen-expiry-${state.tone}`}>{state.label}</span></div>; })}{!visibleInventory.length ? inventoryLoading ? <div className="kitchen-fridge-loading" aria-label="Loading fridge inventory"><span /><span /><span /><span /><span /></div> : <div className="kitchen-fridge-empty"><Refrigerator size={32} strokeWidth={1.25} /><p>{inventoryError ? "We couldn’t load your fridge." : "Your fridge is empty."}</p><button type="button" onClick={() => onOpen("fridge-inventory")}>{inventoryError ? "Open fridge controls" : "Add an ingredient"}</button></div> : null}</div></section>

      <div className="kitchen-side-stack"><NutritionStatus nutrition={status?.nutrition} loading={nutritionLoading} error={nutritionError} onOpen={() => onOpen("nutrition")} /><section className="kitchen-panel kitchen-quick" aria-label="Quick actions"><div className="kitchen-panel-head"><div><Sparkles size={19} /><h2>Quick actions</h2></div></div><div className="kitchen-quick-grid"><button type="button" onClick={() => onOpen("external-meal")}><Utensils size={20} /><span>Log external meal</span></button><button type="button" onClick={() => onOpen("fridge-inventory")}><Plus size={20} /><span>Add ingredient</span></button><button type="button" onClick={() => onOpen("receipt-inbox")}><ReceiptText size={20} /><span>Scan receipt</span></button></div></section></div>

      <section className="kitchen-panel kitchen-week" aria-label="This week's meals"><div className="kitchen-panel-head"><div><Utensils size={19} /><h2>This week’s meals</h2></div><button type="button" onClick={() => onOpen("planned-meals")}>View all <span aria-hidden="true">↗</span></button></div><p className="kitchen-panel-caption">{activePlans.filter((plan) => weekDays(today).some((day) => dateKey(day) === dateKey(plan.planned_for))).length} planned this week</p><div className="kitchen-week-strip">{weekDays(today).map((day) => { const dayPlans = activePlans.filter((plan) => dateKey(plan.planned_for) === dateKey(day)); return <button className={`kitchen-day ${dateKey(day) === todayKey ? "is-today" : ""} ${dayPlans.length ? "has-plan" : ""}`} type="button" key={dateKey(day)} onClick={() => onOpen("planned-meals")}><span>{day.toLocaleDateString(undefined, { weekday: "short" })}</span><strong>{day.getDate()}</strong><small>{dayPlans[0]?.recipe.name ?? "No meal planned"}</small>{dayPlans.length > 1 ? <em>+{dayPlans.length - 1}</em> : null}</button>; })}</div></section>

      <section className="kitchen-panel kitchen-shopping" aria-label="Shopping connection"><div className="kitchen-panel-head"><div><ShoppingCart size={19} /><h2>Shopping connection</h2></div><button type="button" onClick={() => onOpen("shopping")}>Open list <span aria-hidden="true">↗</span></button></div>{shoppingLoading || shoppingError ? <div className="kitchen-shopping-state"><ShoppingCart size={38} strokeWidth={1.2} /><p>{shoppingLoading ? "Checking your shopping list…" : "Shopping list unavailable."}</p></div> : <><strong>{shoppingCount}</strong><p>{shoppingCount === 1 ? "item" : "items"} on your kitchen shopping list</p><div className="kitchen-shopping-preview">{shopping.slice(0, 3).map((item) => <span key={`${item.ingredient_name}-${item.unit}`}>{item.ingredient_name}</span>)}{!shopping.length ? <span>{activeShoppingNeeds.length ? "Review shopping needs below" : "No active shopping needs"}</span> : null}</div></>}</section>
    </div>
  </div>;
}
