# V0.8 Kitchen Report

## 1. Release Purpose
V0.8 turns Kitchen from a placeholder into a deterministic specialist domain for inventory, recipes, nutrition targets/progress, meal history, recommendations, shopping needs, and Chef context.

## 2. Scope Boundary
Implemented V0.8 Kitchen only. V0.9 memory/learning, grocery delivery, medical nutrition, external calendar ownership, and autonomous scheduling were not implemented.

## 3. Preconditions
V0.1 through V0.7 were already implemented. The V0.7 Assistant boundary and planner Action pool were reused.

## 4. Repository Audit
The previous Kitchen implementation only supported simple inventory rows. Existing planner, action, event, outbox, world revision, assistant, and frontend patterns were available.

## 5. Architecture Reused
The implementation reuses FastAPI routers, SQLAlchemy models, Alembic migrations, canonical service modules, React Query API patterns, and the existing Action-to-PlanBlock planner bridge.

## 6. New Database Migration
Migration `0008_kitchen` adds V0.8 Kitchen tables and extends `kitchen_inventory_items` while preserving legacy fields.

## 7. Inventory Identity
`kitchen_inventory_items` now represents ingredient identity with canonical unit, active flag, category, storage hint, and compatibility fields.

## 8. Inventory Lots
`kitchen_inventory_lots` is the source of stock truth. Quantities are decremented on lots, not directly on recipe plans.

## 9. Expiry Categories
Inventory reads expose `expired`, `expires_today`, `expires_soon`, `later`, or `no_expiry` using a 3-day soon window.

## 10. Unit Model
Supported units are `g`, `kg`, `ml`, `l`, `count`, and `serving`, with compatibility aliases for legacy count-like units such as `tub`.

## 11. Unit Conversion
Mass converts through grams; volume converts through milliliters. Count and serving are separate families.

## 12. Unit Rejection
Incompatible subtraction, such as grams from count lots, is rejected with a semantic error before inventory mutation.

## 13. Recipe Model
`kitchen_recipes` stores name, timing, servings, nutrition per serving, protein family, difficulty, tags, active state, and notes.

## 14. Recipe Ingredients
`kitchen_recipe_ingredients` stores required/optional ingredients, quantity/unit, optional item link, substitution group, and order.

## 15. Nutrition Targets
`kitchen_nutrition_targets` stores active/superseded calories and protein targets with effective dates.

## 16. Nutrition Progress
Daily nutrition progress derives from `kitchen_meal_history` for the current local day and reports consumed, remaining, and over-target values.

## 17. Meal History
`kitchen_meal_history` snapshots consumed recipe/manual meals, servings, calories, protein, optional carbs/fat, source, satisfaction, and optional PlanBlock link.

## 18. Recipe Completion
Recipe completion validates recipe ownership, serving count, inventory availability, and units; then consumes inventory and creates a meal history record in one transaction.

## 19. Consumption Ordering
Consumption is deterministic: earliest expiry first, then earliest purchased/created lot. Inventory cannot go negative.

## 20. Manual Meals
Manual/external meals update nutrition progress without decrementing inventory.

## 21. Preference Evidence
`kitchen_preference_evidence` stores deterministic signals such as meal satisfaction. No learned V0.9 model was added.

## 22. Shopping Needs
`kitchen_shopping_needs` and items represent deduped missing-ingredient needs generated from forecast recommendations.

## 23. Forecast Window
Shopping forecast supports a 3-7 day window and dedupes active needs by recipe metadata.

## 24. Planner Bridge
Shopping needs sync to normal `actions` with `domain="kitchen"`, `level="maintenance"`, context `shopping`, deadlines, duration bounds, and planner metadata.

## 25. PlanBlock Boundary
Kitchen never writes `plan_blocks`. Only the Core Planner may schedule Kitchen candidate Actions.

## 26. Recommendation Engine
Recommendations are deterministic and generated in the Kitchen service.

## 27. Scoring Formula
`score = preference_fit + nutrition_fit + inventory_fit + craving_context_fit + cooking_skill_progress + ingredient_expiry_value + variety_value - repeat_penalty - shopping_friction - time_cost - waste_risk`.

## 28. Factor Bounds
Factors are named, numeric, bounded in implementation, and returned to the API as `score_factors`.

## 29. Nutrition Fit
Nutrition fit considers today's remaining calories and protein against recipe nutrition per serving.

## 30. Inventory Fit
Inventory fit rewards required ingredients available in compatible units.

## 31. Expiry Value
Ingredient expiry value rewards recipes that consume lots expiring within the 3-day soon window.

## 32. Shopping Friction
Missing required ingredients add shopping friction and appear as `missing_ingredients`.

## 33. Time Cost
Preparation plus cooking time reduces score, with extra cost when a max-minute filter is exceeded.

## 34. Variety
Recent same recipe and same protein family add repeat penalty; absence of recent family use adds variety value.

## 35. No-Shopping Mode
No-shopping mode filters recommendations to inventory-available recipes only.

## 36. No-Shopping Fallback
If no inventory meal fits, the API returns an empty deterministic result instead of inventing a meal.

## 37. Chef Context
Chef context includes Kitchen status, no-shopping recommendations, active shopping needs, allowed tools, and the planner boundary.

## 38. Assistant Role
Assistant role `CHEF` was added. Chef can read Kitchen status/recommendations/needs and propose confirmed meal mutations.

## 39. Assistant Tools
New tools include `get_kitchen_status`, `get_kitchen_recommendations`, `get_shopping_needs`, `log_manual_meal`, and `complete_recipe_meal`.

## 40. AI Boundary
Chef does not score meals with AI, create PlanBlocks, bypass confirmation, invent nutrition history, or order groceries.

## 41. API Surface
Added Kitchen endpoints for status, chef context, inventory lots, recipes, recipe completion, manual meals, nutrition targets/progress, recommendations, shopping forecast, shopping needs, and shopping Action sync.

## 42. Frontend Dashboard
The Kitchen page now shows nutrition targets/progress, inventory lots/expiry, meal logging, deterministic recommendations, recipe creation, shopping needs, and sync actions.

## 43. Home Card
Home now includes Kitchen status beside Learning and Fitness.

## 44. Assistant UI
Assistant role picker now includes Chef.

## 45. Events
Kitchen mutations emit semantic events such as `kitchen.inventory.changed`, `kitchen.recipe.created`, `kitchen.meal.completed`, `kitchen.nutrition_target.updated`, and `kitchen.shopping_need.created`.

## 46. WorldRevision
Canonical Kitchen mutations use `append_event`, outbox, and world revision semantics.

## 47. Idempotency
Kitchen direct endpoints do not add new idempotency wrappers in V0.8; assistant-confirmed Kitchen mutations use the existing proposal confirmation replay layer.

## 48. Backward Compatibility
Legacy inventory POST/GET still works. Count-like legacy units are normalized to `count`.

## 49. Backend Tests
New tests cover lot consumption order, expiry scoring, nutrition progress, manual meals, shopping forecast dedupe, candidate Action sync, no-shopping filtering, and Chef reads.

## 50. Frontend Tests
New Kitchen tests cover dashboard rendering, inventory creation, meal logging, recommendation completion, recipe creation, forecast, and action sync. Home mocks were updated for Kitchen status.

## 51. Regression Tests
Full backend suite passes: `69 passed, 2 warnings`. Frontend suite passes: `40 passed`.

## 52. Typecheck
Frontend TypeScript typecheck passes.

## 53. Build
Frontend production build passes.

## 54. Migration Acceptance
`alembic upgrade head` applied `0007_assistant -> 0008_kitchen` cleanly on PostgreSQL.

## 55. Live Smoke
After backend restart, HTTP smoke created a target, inventory item, recipe, no-shopping recommendation, and completed meal. Nutrition protein consumed updated to `35.0`.

## 56. Release Decision
PASS
