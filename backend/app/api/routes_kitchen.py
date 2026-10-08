from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.actions.schemas import ActionRead
from app.api.deps import get_current_user
from app.core.config import get_settings
from app.database.models import UserProfile
from app.database.session import get_db
from app.domains.kitchen import service
from app.domains.kitchen.chef import recommend_from_text
from app.domains.kitchen.schemas import (
    InventoryItemCreate,
    InventoryItemRead,
    InventoryLotCreate,
    InventoryMutationCreate,
    InventoryStapleUpdate,
    KitchenStatusRead,
    ChefRecommendationSetRead,
    ChefIntentRecommendationRead,
    ChefIntentRequest,
    CompetencyRead,
    MealCompleteRequest,
    MealChoiceOutcomeRequest,
    MealHistoryRead,
    MealPlanCompleteRequest,
    MealPlanRead,
    MealPlanModifyRequest,
    MealSelectionCreate,
    MealManualCreate,
    MealRecommendationRead,
    NutritionProgressRead,
    NutritionTargetRead,
    NutritionTargetUpsert,
    RecipeCreate,
    RecipeRead,
    RecommendationRequest,
    ShoppingForecastRequest,
    ShoppingAggregateRead,
    ShoppingNeedItemRead,
    ShoppingNeedRead,
    ShoppingPurchaseCreate,
    CookingSessionStartRequest,
    CookingSessionUpdateRequest,
)
from app.memory.schemas import RecommendationOutcomeRead
from app.workspaces.schemas import ActiveWorkspaceRead

router = APIRouter(prefix="/kitchen", tags=["kitchen"])


@router.get("/status", response_model=KitchenStatusRead)
def kitchen_status(db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    return service.status_summary(db, user)


@router.get("/chef-context")
def kitchen_chef_context(db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    return service.chef_context(db, user)


@router.post("/inventory", response_model=InventoryItemRead)
def create_inventory_item(payload: InventoryItemCreate, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    item = service.add_inventory_item(db, user, payload)
    db.commit()
    return item


@router.get("/inventory", response_model=list[InventoryItemRead])
def get_inventory(db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    return service.list_inventory(db, user)


@router.post("/inventory/{item_id}/lots", response_model=InventoryItemRead)
def create_inventory_lot(item_id: str, payload: InventoryLotCreate, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    item = service.add_inventory_lot(db, user, item_id, payload)
    db.commit()
    return item


@router.post("/inventory/{item_id}/mutations", response_model=InventoryItemRead)
def mutate_inventory(item_id: str, payload: InventoryMutationCreate, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    item = service.mutate_inventory(db, user, item_id, payload)
    db.commit()
    return item


@router.patch("/inventory/{item_id}/staple", response_model=InventoryItemRead)
def configure_inventory_staple(item_id: str, payload: InventoryStapleUpdate, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    item = service.update_inventory_staple(db, user, item_id, payload)
    db.commit()
    return item


@router.post("/recipes", response_model=RecipeRead)
def create_recipe(payload: RecipeCreate, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    recipe = service.create_recipe(db, user, payload)
    db.commit()
    return recipe


@router.get("/recipes", response_model=list[RecipeRead])
def list_recipes(db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    return service.list_recipes(db, user)


@router.get("/recipes/{recipe_id}", response_model=RecipeRead)
def get_recipe(recipe_id: str, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    return service.get_recipe(db, user, recipe_id)


@router.post("/recipes/{recipe_id}/complete", response_model=MealHistoryRead)
def complete_recipe_meal(recipe_id: str, payload: MealCompleteRequest, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    meal = service.complete_recipe_meal(db, user, recipe_id, payload)
    db.commit()
    return meal


@router.post("/meals/manual", response_model=MealHistoryRead)
def log_manual_meal(payload: MealManualCreate, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    meal = service.log_manual_meal(db, user, payload)
    db.commit()
    return meal


@router.get("/nutrition-target", response_model=NutritionTargetRead | None)
def get_nutrition_target(db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    return service.get_active_nutrition_target(db, user)


@router.post("/nutrition-target", response_model=NutritionTargetRead)
@router.put("/nutrition-target", response_model=NutritionTargetRead)
def upsert_nutrition_target(payload: NutritionTargetUpsert, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    target = service.upsert_nutrition_target(db, user, payload)
    db.commit()
    return target


@router.get("/nutrition/progress", response_model=NutritionProgressRead)
def nutrition_progress(db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    return service.daily_nutrition_progress(db, user)


@router.get("/recommendations", response_model=list[MealRecommendationRead])
def get_recommendations(
    no_shopping: bool = False,
    craving: str | None = None,
    max_minutes: int | None = Query(default=None, gt=0),
    limit: int = Query(default=5, ge=1, le=20),
    db: Session = Depends(get_db),
    user: UserProfile = Depends(get_current_user),
):
    return service.recommendations(db, user, RecommendationRequest(no_shopping=no_shopping, craving=craving, max_minutes=max_minutes, limit=limit))


@router.post("/chef/recommendations", response_model=ChefRecommendationSetRead)
def prepare_recommendations(payload: RecommendationRequest, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    result = service.recommendation_set(db, user, payload)
    db.commit()
    return result


@router.post("/chef/recommend", response_model=ChefIntentRecommendationRead)
def recommend_meal_from_text(payload: ChefIntentRequest, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    result = recommend_from_text(db, user, payload, get_settings())
    db.commit()
    return result


@router.post("/chef/recommendations/{recommendation_id}/options/{option_id}/reject", response_model=RecommendationOutcomeRead)
def reject_recommendation(recommendation_id: str, option_id: str, payload: MealChoiceOutcomeRequest, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    result = service.reject_meal(db, user, recommendation_id, option_id, payload.feedback)
    db.commit()
    return result


@router.post("/meal-plans", response_model=MealPlanRead)
def select_meal(payload: MealSelectionCreate, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    result = service.select_meal(db, user, payload)
    db.commit()
    return result


@router.get("/meal-plans", response_model=list[MealPlanRead])
def meal_plans(db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    return service.list_meal_plans(db, user)


@router.patch("/meal-plans/{plan_id}", response_model=MealPlanRead)
def modify_meal_plan(plan_id: str, payload: MealPlanModifyRequest, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    result = service.modify_meal_plan(db, user, plan_id, payload)
    db.commit()
    return result


@router.post("/cooking-sessions", response_model=ActiveWorkspaceRead)
def start_cooking_session(payload: CookingSessionStartRequest, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    result = service.start_cooking_session(db, user, payload)
    db.commit()
    return result


@router.patch("/cooking-sessions/{workspace_id}", response_model=ActiveWorkspaceRead)
def update_cooking_session(workspace_id: str, payload: CookingSessionUpdateRequest, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    result = service.update_cooking_session(db, user, workspace_id, payload)
    db.commit()
    return result


@router.post("/meal-plans/{plan_id}/complete", response_model=MealPlanRead)
def complete_meal_plan(plan_id: str, payload: MealPlanCompleteRequest, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    result = service.complete_meal_plan(db, user, plan_id, payload)
    db.commit()
    return result


@router.get("/competencies", response_model=list[CompetencyRead])
def cooking_competencies(db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    return service.list_competencies(db, user)


@router.post("/shopping-forecast", response_model=list[ShoppingNeedRead])
def create_shopping_forecast(payload: ShoppingForecastRequest, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    needs = service.create_shopping_forecast(db, user, payload)
    db.commit()
    return needs


@router.get("/shopping-needs", response_model=list[ShoppingNeedRead])
def list_shopping_needs(active_only: bool = True, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    return service.list_shopping_needs(db, user, active_only=active_only)


@router.get("/shopping-list", response_model=list[ShoppingAggregateRead])
def shopping_list(db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    return service.aggregated_shopping_list(db, user)


@router.post("/shopping-items/{item_id}/purchase", response_model=ShoppingNeedItemRead)
def purchase_shopping_item(item_id: str, payload: ShoppingPurchaseCreate, db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    result = service.mark_shopping_item_purchased(db, user, item_id, payload)
    db.commit()
    return result


@router.post("/shopping-needs/sync-actions", response_model=list[ActionRead])
def sync_shopping_actions(db: Session = Depends(get_db), user: UserProfile = Depends(get_current_user)):
    actions = service.sync_shopping_actions(db, user)
    db.commit()
    return actions
