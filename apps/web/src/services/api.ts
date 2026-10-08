import { clearAuthToken, getValidAuthToken } from "../lib/auth";
import { consumeAssistantStream } from "./assistantStream";
import type {
  BodyMeasurement,
  ActionIntention,
  AssistantActionProposal,
  AssistantResponse,
  AssistantRole,
  CalendarProjection,
  Commitment,
  ConversationThread,
  ConversationThreadDetail,
  ControlStatus,
  DecisionFactor,
  Course,
  Exercise,
  ExerciseSet,
  Exam,
  FitnessCandidate,
  FitnessGoal,
  FitnessStatus,
  GoalsOverview,
  Goal,
  HouseholdOverview,
  HouseholdTask,
  InventoryItem,
  HorizonAllocation,
  KitchenStatus,
  LearningCandidate,
  LearningStatus,
  LatestState,
  MealHistory,
  MealPlan,
  MealRecommendation,
  ChefRecommendationSet,
  ChefIntentRecommendation,
  ActiveWorkspace,
  MorningBriefing,
  CookingCompetency,
  ReceiptImport,
  ShoppingAggregate,
  FinanceOverview,
  FinanceImportBatch,
  FinanceBudget,
  FeedbackSessionState,
  MemoryItem,
  MemoryDetail,
  NutritionProgress,
  NutritionTarget,
  Plan,
  PlanProposal,
  PatternEvidence,
  PersonalModelSummary,
  PersonalModelVersion,
  PushSubscriptionRead,
  ProgressionState,
  ReadinessSummary,
  RecoveryObservation,
  ReplanResponse,
  Recipe,
  ShoppingNeed,
  StateObservationBatch,
  StudySession,
  StudyTopic,
  WorkoutProgram,
  WorkoutSession,
  WorkoutTemplate,
  WorkoutTemplateExercise
  , NotebookEntry, NotebookSearchResult, StandingCalendarRule, FixtureBinding, FixtureSyncSummary,
  LeisureTrajectory, Movie, MovieWatchlistItem, MovieViewing, MovieRecommendation, MovieImportBatch,
  SocialTrajectory, Opportunity, OpportunityRecommendation, OpportunitySource, SocialActivity,
  QuickCapture, ReviewItem, IntelligenceControlSurface, IntelligenceSettings, AgentSettings,
  AgentProfile, AgentWorkActivity,
  EmbeddingSettings, EmbeddingConnectionTest, OpenAIChatTest, JevDecisionTest
} from "../types/api";

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

async function apiRequest<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = await getValidAuthToken();
  const response = await fetch(`${API_BASE_URL}/api/v1${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers
    }
  });

  if (response.status === 401) {
    clearAuthToken();
    window.dispatchEvent(new Event("life-os:auth-expired"));
  }

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(errorBody.detail ?? response.statusText);
  }

  if (response.status === 204) {
    return null as T;
  }

  return response.json() as Promise<T>;
}

export const api = {
  me: () => apiRequest<{ id: string; email: string; display_name: string; world_revision: number; version: number }>("/me"),
  latestState: () => apiRequest<LatestState>("/state/latest"),
  createStateObservations: (payload: { energy: number; mental_state: number }) =>
    apiRequest<StateObservationBatch>("/state/observations", {
      method: "POST",
      headers: { "Idempotency-Key": crypto.randomUUID() },
      body: JSON.stringify(payload)
    }),
  bodyMeasurements: () => apiRequest<BodyMeasurement[]>("/fitness/body-measurements"),
  latestBodyMeasurement: () => apiRequest<BodyMeasurement>("/fitness/body-measurements/latest"),
  addBodyMeasurement: (payload: Partial<BodyMeasurement>) =>
    apiRequest<BodyMeasurement>("/fitness/body-measurements", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  fitnessStatus: () => apiRequest<FitnessStatus>("/fitness/status"),
  bodyTrends: () => apiRequest<FitnessStatus["body_trend"]>("/fitness/body-trends"),
  addFitnessGoal: (payload: Partial<FitnessGoal>) =>
    apiRequest<FitnessGoal>("/fitness/goals", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  fitnessPrograms: () => apiRequest<WorkoutProgram[]>("/fitness/programs"),
  createFitnessProgram: (payload: { name: string; goal_type?: string | null; description?: string | null; active?: boolean }) =>
    apiRequest<WorkoutProgram>("/fitness/programs", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  updateFitnessProgram: (id: string, payload: Partial<WorkoutProgram> & { expected_version?: number | null }) =>
    apiRequest<WorkoutProgram>(`/fitness/programs/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload)
    }),
  fitnessExercises: () => apiRequest<Exercise[]>("/fitness/exercises"),
  createFitnessExercise: (payload: {
    name: string;
    category?: string | null;
    primary_muscle_group?: string | null;
    equipment?: string | null;
    default_rest_seconds?: number;
  }) =>
    apiRequest<Exercise>("/fitness/exercises", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  fitnessTemplates: () => apiRequest<WorkoutTemplate[]>("/fitness/templates"),
  createFitnessTemplate: (payload: {
    program_id: string;
    name: string;
    sequence_order?: number;
    estimated_duration_minutes?: number;
    active?: boolean;
  }) =>
    apiRequest<WorkoutTemplate>("/fitness/templates", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  addFitnessTemplateExercise: (
    templateId: string,
    payload: {
      exercise_id: string;
      order_index?: number;
      target_sets?: number;
      target_rep_min?: number;
      target_rep_max?: number;
      target_load_kg?: number | null;
      target_rpe?: number | null;
      rest_seconds?: number;
      load_increment_kg?: number;
    }
  ) =>
    apiRequest<WorkoutTemplateExercise>(`/fitness/templates/${templateId}/exercises`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  activeWorkoutSession: () => apiRequest<WorkoutSession | null>("/fitness/sessions/active"),
  startWorkout: (payload: { workout_template_id: string; source_action_id?: string | null; source_plan_block_id?: string | null }) =>
    apiRequest<WorkoutSession>("/fitness/sessions/start", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  logWorkoutSet: (
    sessionId: string,
    payload: { template_exercise_id: string; reps: number; load_kg: number; rpe: number; set_type?: string; note?: string | null }
  ) =>
    apiRequest<ExerciseSet>(`/fitness/sessions/${sessionId}/sets`, {
      method: "POST",
      headers: { "Idempotency-Key": crypto.randomUUID() },
      body: JSON.stringify(payload)
    }),
  completeWorkout: (sessionId: string, payload: { perceived_session_difficulty?: number | null; notes?: string | null } = {}) =>
    apiRequest<WorkoutSession>(`/fitness/sessions/${sessionId}/complete`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  abandonWorkout: (sessionId: string, payload: { notes?: string | null } = {}) =>
    apiRequest<WorkoutSession>(`/fitness/sessions/${sessionId}/abandon`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  addRecoveryObservation: (payload: { soreness?: number | null; sleep_quality?: number | null; stress?: number | null; readiness?: number | null }) =>
    apiRequest<RecoveryObservation>("/fitness/recovery", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  readinessSummary: () => apiRequest<ReadinessSummary>("/fitness/readiness/summary"),
  fitnessCandidates: () => apiRequest<FitnessCandidate[]>("/fitness/candidates"),
  syncFitnessCandidateActions: () => apiRequest<ActionIntention[]>("/fitness/candidates/sync-actions", { method: "POST" }),
  fitnessProgression: () => apiRequest<ProgressionState[]>("/fitness/progression"),
  learningStatus: () => apiRequest<LearningStatus>("/learning/status"),
  goalsOverview: () => apiRequest<GoalsOverview>("/goals/overview"),
  createGoal: (payload: { title: string; domain: string; description?: string | null; priority?: number; target_date?: string | null; success_condition?: string | null; progress_mode?: string; manual_progress?: number | null; source_entity_type?: string | null; source_entity_id?: string | null }) =>
    apiRequest<Goal>("/goals", { method: "POST", body: JSON.stringify(payload) }),
  householdOverview: () => apiRequest<HouseholdOverview>("/home/overview"),
  createHouseholdTask: (payload: { title: string; category?: string; recurrence: Record<string, unknown>; estimated_duration_minutes: number; minimum_duration_minutes: number; location?: string; priority?: number; next_due_at?: string | null; notes?: string | null }) =>
    apiRequest<HouseholdTask>("/home/tasks", { method: "POST", body: JSON.stringify(payload) }),
  completeHouseholdTask: (taskId: string, expectedVersion: number) =>
    apiRequest<HouseholdTask>(`/home/tasks/${taskId}/complete`, { method: "POST", body: JSON.stringify({ expected_version: expectedVersion }) }),
  learningCourses: () => apiRequest<Course[]>("/learning/courses"),
  createLearningCourse: (payload: { name: string; code?: string | null; description?: string | null; institution?: string | null }) =>
    apiRequest<Course>("/learning/courses", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  exams: () => apiRequest<Exam[]>("/learning/exams"),
  addExam: (payload: {
    course_id?: string | null;
    title: string;
    exam_at?: string | null;
    exam_date?: string | null;
    target_preparation_minutes?: number;
    estimated_required_hours?: number;
    importance: string;
  }) =>
    apiRequest<Exam>("/learning/exams", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  addLearningTopic: (examId: string, payload: { title: string; order_index?: number; importance_weight?: number; estimated_required_minutes?: number | null; prerequisite_topic_id?: string | null }) =>
    apiRequest<StudyTopic>(`/learning/exams/${examId}/topics`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  logStudySession: (payload: {
    exam_id: string;
    topic_id?: string | null;
    duration_minutes: number;
    quality_rating?: number | null;
    source?: string;
    notes?: string | null;
  }) =>
    apiRequest<StudySession>("/learning/study-sessions", {
      method: "POST",
      headers: { "Idempotency-Key": crypto.randomUUID() },
      body: JSON.stringify(payload)
    }),
  learningCandidates: () => apiRequest<LearningCandidate[]>("/learning/candidates"),
  syncLearningCandidateActions: () => apiRequest<ActionIntention[]>("/learning/candidates/sync-actions", { method: "POST" }),
  kitchenStatus: () => apiRequest<KitchenStatus>("/kitchen/status"),
  personalModelSummary: () => apiRequest<PersonalModelSummary>("/personal-model/summary"),
  personalModels: () => apiRequest<PersonalModelVersion[]>("/personal-model/models"),
  personalPatterns: () => apiRequest<PatternEvidence[]>("/personal-model/patterns"),
  refreshPersonalModels: () => apiRequest<{ id: string; status: string; evidence_n: number; metrics_json: Record<string, unknown> }>("/personal-model/refresh", { method: "POST" }),
  correctPersonalPattern: (patternId: string, payload: { reason?: string; note?: string | null } = {}) =>
    apiRequest<PatternEvidence>(`/personal-model/patterns/${patternId}/correct`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  memories: (filters: { domain?: string; memoryType?: string; status?: string } = {}) => {
    const params = new URLSearchParams();
    if (filters.domain) params.set("domain", filters.domain);
    if (filters.memoryType) params.set("memory_type", filters.memoryType);
    if (filters.status) params.set("status", filters.status);
    const query = params.toString();
    return apiRequest<MemoryItem[]>(`/memories${query ? `?${query}` : ""}`);
  },
  memoryDetail: (memoryId: string) => apiRequest<MemoryDetail>(`/memories/${memoryId}`),
  createMemory: (payload: { content: string; memory_type?: string; domain?: string; polarity?: number; importance?: number; pinned?: boolean }) =>
    apiRequest<MemoryItem>("/memories", { method: "POST", body: JSON.stringify(payload) }),
  updateMemory: (memoryId: string, payload: { content?: string; memory_type?: string; domain?: string; polarity?: number; importance?: number; expected_version?: number }) =>
    apiRequest<MemoryItem>(`/memories/${memoryId}`, { method: "PATCH", body: JSON.stringify(payload) }),
  pinMemory: (memoryId: string, pinned: boolean) =>
    apiRequest<MemoryItem>(`/memories/${memoryId}/${pinned ? "pin" : "unpin"}`, { method: "POST" }),
  confirmMemory: (memoryId: string) => apiRequest<MemoryItem>(`/memories/${memoryId}/confirm`, { method: "POST" }),
  forgetMemory: (memoryId: string) => apiRequest<MemoryItem>(`/memories/${memoryId}/forget`, { method: "POST" }),
  inventory: () => apiRequest<InventoryItem[]>("/kitchen/inventory"),
  addInventoryItem: (payload: { ingredient_name: string; quantity: number; unit: string; expires_on?: string | null; canonical_unit?: string; is_staple?: boolean; restock_threshold?: number | null; restock_target?: number | null }) =>
    apiRequest<InventoryItem>("/kitchen/inventory", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  mutateInventory: (itemId: string, payload: { operation: "add" | "consume" | "adjust" | "discard" | "expire" | "reconcile"; quantity: number; unit: string; reason?: string | null }) =>
    apiRequest<InventoryItem>(`/kitchen/inventory/${itemId}/mutations`, { method: "POST", body: JSON.stringify(payload) }),
  configureInventoryStaple: (itemId: string, payload: { is_staple: boolean; restock_threshold?: number | null; restock_target?: number | null }) =>
    apiRequest<InventoryItem>(`/kitchen/inventory/${itemId}/staple`, { method: "PATCH", body: JSON.stringify(payload) }),
  kitchenRecipes: () => apiRequest<Recipe[]>("/kitchen/recipes"),
  createKitchenRecipe: (payload: {
    name: string;
    preparation_minutes?: number;
    cooking_minutes?: number;
    servings?: number;
    calories_per_serving?: number;
    protein_g_per_serving?: number;
    protein_family?: string | null;
    tags?: string[];
    steps?: string[];
    techniques?: Array<{ key: string; name: string; required_level?: number; importance?: number }>;
    ingredients: Array<{ ingredient_name: string; quantity: number; unit: string; optional?: boolean }>;
  }) =>
    apiRequest<Recipe>("/kitchen/recipes", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  kitchenRecommendations: (params: { no_shopping?: boolean; craving?: string | null; max_minutes?: number | null; limit?: number } = {}) => {
    const search = new URLSearchParams();
    if (params.no_shopping != null) search.set("no_shopping", String(params.no_shopping));
    if (params.craving) search.set("craving", params.craving);
    if (params.max_minutes) search.set("max_minutes", String(params.max_minutes));
    if (params.limit) search.set("limit", String(params.limit));
    return apiRequest<MealRecommendation[]>(`/kitchen/recommendations${search.size ? `?${search.toString()}` : ""}`);
  },
  chefRecommendations: (payload: { no_shopping?: boolean; craving?: string | null; max_minutes?: number | null; limit?: number } = {}) =>
    apiRequest<ChefRecommendationSet>("/kitchen/chef/recommendations", { method: "POST", body: JSON.stringify(payload) }),
  recommendMealFromText: (payload: { request: string; servings?: number; max_total_minutes?: number; inventory_preference?: "USE_WHAT_I_HAVE" | "MINIMAL_SHOPPING" | "SHOPPING_ALLOWED"; limit?: number }) =>
    apiRequest<ChefIntentRecommendation>("/kitchen/chef/recommend", { method: "POST", body: JSON.stringify(payload) }),
  rejectMealRecommendation: (recommendationId: string, optionId: string, feedback?: string | null) =>
    apiRequest(`/kitchen/chef/recommendations/${recommendationId}/options/${optionId}/reject`, { method: "POST", body: JSON.stringify({ feedback }) }),
  selectMeal: (payload: { recommendation_id: string; option_id: string; planned_for: string; meal_type?: string; servings?: number }) =>
    apiRequest<MealPlan>("/kitchen/meal-plans", { method: "POST", body: JSON.stringify(payload) }),
  mealPlans: () => apiRequest<MealPlan[]>("/kitchen/meal-plans"),
  modifyMealPlan: (planId: string, payload: { servings?: number; excluded_ingredients?: string[]; ingredient_substitutions?: Record<string, string> }) =>
    apiRequest<MealPlan>(`/kitchen/meal-plans/${planId}`, { method: "PATCH", body: JSON.stringify(payload) }),
  startCookingSession: (mealPlanId: string) => apiRequest<ActiveWorkspace>("/kitchen/cooking-sessions", { method: "POST", body: JSON.stringify({ meal_plan_id: mealPlanId }) }),
  updateCookingSession: (workspaceId: string, payload: { current_step_index?: number; timer_refs?: string[]; equipment_refs?: string[]; ingredient_changes?: string[]; temporary_notes?: string }) =>
    apiRequest<ActiveWorkspace>(`/kitchen/cooking-sessions/${workspaceId}`, { method: "PATCH", body: JSON.stringify(payload) }),
  completeMealPlan: (planId: string, payload: { satisfaction?: number | null; feedback?: string | null }) =>
    apiRequest<MealPlan>(`/kitchen/meal-plans/${planId}/complete`, { method: "POST", body: JSON.stringify(payload) }),
  cookingCompetencies: () => apiRequest<CookingCompetency[]>("/kitchen/competencies"),
  completeKitchenRecipe: (recipeId: string, payload: { servings?: number; satisfaction?: number | null; notes?: string | null } = {}) =>
    apiRequest<MealHistory>(`/kitchen/recipes/${recipeId}/complete`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  logManualMeal: (payload: { name: string; calories: number; protein_g: number; servings?: number; satisfaction?: number | null }) =>
    apiRequest<MealHistory>("/kitchen/meals/manual", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  nutritionProgress: () => apiRequest<NutritionProgress>("/kitchen/nutrition/progress"),
  nutritionTarget: () => apiRequest<NutritionTarget | null>("/kitchen/nutrition-target"),
  upsertNutritionTarget: (payload: { calories_target: number; protein_g_target: number; source?: string }) =>
    apiRequest<NutritionTarget>("/kitchen/nutrition-target", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  shoppingNeeds: () => apiRequest<ShoppingNeed[]>("/kitchen/shopping-needs"),
  shoppingList: () => apiRequest<ShoppingAggregate[]>("/kitchen/shopping-list"),
  markShoppingPurchased: (itemId: string, payload: { quantity?: number; unit?: string; add_to_inventory?: boolean } = {}) =>
    apiRequest(`/kitchen/shopping-items/${itemId}/purchase`, { method: "POST", body: JSON.stringify(payload) }),
  createShoppingForecast: (payload: { window_days?: number; limit?: number } = {}) =>
    apiRequest<ShoppingNeed[]>("/kitchen/shopping-forecast", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  syncKitchenShoppingActions: () => apiRequest<ActionIntention[]>("/kitchen/shopping-needs/sync-actions", { method: "POST" }),
  receipts: () => apiRequest<ReceiptImport[]>("/receipts"),
  createReceipt: (payload: { filename: string; mime_type: string; content_base64: string; process?: boolean }) =>
    apiRequest<ReceiptImport>("/receipts", { method: "POST", body: JSON.stringify(payload) }),
  reviewReceipt: (receiptId: string, payload: Record<string, unknown>) =>
    apiRequest<ReceiptImport>(`/receipts/${receiptId}`, { method: "PATCH", body: JSON.stringify(payload) }),
  confirmReceipt: (receiptId: string) => apiRequest<ReceiptImport>(`/receipts/${receiptId}/confirm`, { method: "POST" }),
  processReceipt: (receiptId: string) => apiRequest<ReceiptImport>(`/receipts/${receiptId}/process`, { method: "POST" }),
  financeOverview: () => apiRequest<FinanceOverview>("/finance/overview"),
  createFinanceImport: (payload: { filename: string; content: string; currency?: string; mapping?: Record<string, string> }) =>
    apiRequest<FinanceImportBatch>("/finance/imports", { method: "POST", body: JSON.stringify(payload) }),
  updateFinanceImportRow: (rowId: string, payload: Record<string, unknown>) =>
    apiRequest<FinanceImportBatch>(`/finance/imports/rows/${rowId}`, { method: "PATCH", body: JSON.stringify(payload) }),
  confirmFinanceImport: (batchId: string) => apiRequest<FinanceImportBatch>(`/finance/imports/${batchId}/confirm`, { method: "POST" }),
  saveFinanceBudget: (payload: { name: string; amount: number; category?: string | null; currency?: string; month_start: string; protected?: boolean }) =>
    apiRequest<FinanceBudget>("/finance/budgets", { method: "POST", body: JSON.stringify(payload) }),
  refreshRecurringExpenses: () => apiRequest("/finance/recurring/refresh", { method: "POST" }),
  commitments: () => apiRequest<Commitment[]>("/commitments"),
  notebookEntries: (filters: { entryType?: string; status?: string } = {}) => {
    const params = new URLSearchParams();
    if (filters.entryType) params.set("entry_type", filters.entryType);
    if (filters.status) params.set("status", filters.status);
    const query = params.toString();
    return apiRequest<NotebookEntry[]>(`/notebook${query ? `?${query}` : ""}`);
  },
  searchNotebook: (query: string) => apiRequest<NotebookSearchResult[]>(`/notebook/search?q=${encodeURIComponent(query)}`),
  createNotebookEntry: (payload: { entry_type: "GENERAL" | "IMPLEMENTATION_IDEA"; title: string; content: string; tags?: string[] }) =>
    apiRequest<NotebookEntry>("/notebook", { method: "POST", headers: { "Idempotency-Key": crypto.randomUUID() }, body: JSON.stringify(payload) }),
  reviewNotebookEntry: (id: string) => apiRequest<NotebookEntry>(`/notebook/${id}/review`, { method: "POST" }),
  archiveNotebookEntry: (id: string) => apiRequest<NotebookEntry>(`/notebook/${id}/archive`, { method: "POST" }),
  promoteNotebookEntry: (id: string) => apiRequest(`/notebook/${id}/promote`, { method: "POST", headers: { "Idempotency-Key": crypto.randomUUID() }, body: JSON.stringify({ destination_type: "MANUAL_DEVELOPMENT_REVIEW" }) }),
  standingCalendarRules: () => apiRequest<StandingCalendarRule[]>("/standing-calendar-rules"),
  syncStandingCalendarRule: (id: string) => apiRequest<FixtureSyncSummary>(`/standing-calendar-rules/${id}/sync`, { method: "POST" }),
  setStandingCalendarRuleEnabled: (id: string, enabled: boolean, expectedVersion: number) =>
    apiRequest<StandingCalendarRule>(`/standing-calendar-rules/${id}/enabled`, { method: "PATCH", body: JSON.stringify({ enabled, expected_version: expectedVersion }) }),
  standingRuleFixtures: (id: string) => apiRequest<FixtureBinding[]>(`/standing-calendar-rules/${id}/fixtures`),
  overrideFixture: (id: string, payload: { protected?: boolean; suppressed?: boolean }) =>
    apiRequest<FixtureBinding>(`/standing-calendar-rules/fixtures/${id}/override`, { method: "PATCH", body: JSON.stringify(payload) }),
  addCommitment: (payload: {
    title: string;
    level: string;
    commitment_type: string;
    starts_at: string;
    ends_at: string;
    location?: string | null;
    notes?: string | null;
    recurrence?: Record<string, unknown>;
  }) =>
    apiRequest<Commitment>("/commitments", {
      method: "POST",
      headers: { "Idempotency-Key": crypto.randomUUID() },
      body: JSON.stringify(payload)
    }),
  updateCommitment: (id: string, payload: Partial<Commitment> & { expected_version: number }) =>
    apiRequest<Commitment>(`/commitments/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload)
    }),
  completeCommitment: (id: string, expected_version: number) =>
    apiRequest<Commitment>(`/commitments/${id}/complete`, {
      method: "POST",
      headers: { "Idempotency-Key": crypto.randomUUID() },
      body: JSON.stringify({ expected_version })
    }),
  actions: (planningPool = false) => apiRequest<ActionIntention[]>(`/actions${planningPool ? "?planning_pool=true" : ""}`),
  addAction: (payload: {
    title: string;
    domain: string;
    level: string;
    estimated_minutes: number;
    deadline?: string | null;
    location?: string | null;
    description?: string | null;
  }) =>
    apiRequest<ActionIntention>("/actions", {
      method: "POST",
      headers: { "Idempotency-Key": crypto.randomUUID() },
      body: JSON.stringify(payload)
    }),
  completeAction: (id: string, expected_version: number) =>
    apiRequest<ActionIntention>(`/actions/${id}/complete`, {
      method: "POST",
      headers: { "Idempotency-Key": crypto.randomUUID() },
      body: JSON.stringify({ expected_version })
    }),
  calendarProjection: () => apiRequest<CalendarProjection>("/calendar-projection"),
  currentPlan: (planningDate?: string) =>
    apiRequest<Plan | null>(`/plans/current${planningDate ? `?planning_date=${planningDate}` : ""}`),
  planProposals: () => apiRequest<PlanProposal[]>("/strategy/proposals"),
  presentPlanProposal: (proposalId: string) =>
    apiRequest<PlanProposal>(`/strategy/proposals/${proposalId}/present`, { method: "POST" }),
  acceptPlanProposal: (proposalId: string) =>
    apiRequest<PlanProposal>(`/strategy/proposals/${proposalId}/accept`, { method: "POST" }),
  modifyPlanProposal: (proposalId: string, payload: { requested_target_minutes?: number; protected_block_ids?: string[]; minimum_exam_minutes?: Record<string, number>; note?: string | null }) =>
    apiRequest<PlanProposal>(`/strategy/proposals/${proposalId}/modify`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  rejectPlanProposal: (proposalId: string) =>
    apiRequest<PlanProposal>(`/strategy/proposals/${proposalId}/reject`, { method: "POST" }),
  horizonAllocations: () => apiRequest<HorizonAllocation>("/plans/horizon"),
  generatePlan: (payload: { planning_date?: string; expected_world_revision?: number | null } = {}) =>
    apiRequest<Plan>("/plans/generate", {
      method: "POST",
      headers: { "Idempotency-Key": crypto.randomUUID() },
      body: JSON.stringify(payload)
    }),
  startPlanBlock: (planId: string, blockId: string, expectedVersion: number) =>
    apiRequest<Plan>(`/plans/${planId}/blocks/${blockId}/start`, {
      method: "POST",
      body: JSON.stringify({ expected_version: expectedVersion })
    }),
  completePlanBlock: (planId: string, blockId: string, expectedVersion: number, actualDurationMinutes?: number) =>
    apiRequest<Plan>(`/plans/${planId}/blocks/${blockId}/complete`, {
      method: "POST",
      body: JSON.stringify({ expected_version: expectedVersion, actual_duration_minutes: actualDurationMinutes })
    }),
  partialCompletePlanBlock: (planId: string, blockId: string, expectedVersion: number, actualDurationMinutes: number) =>
    apiRequest<Plan>(`/plans/${planId}/blocks/${blockId}/partial`, {
      method: "POST",
      body: JSON.stringify({ expected_version: expectedVersion, actual_duration_minutes: actualDurationMinutes })
    }),
  skipPlanBlock: (planId: string, blockId: string, expectedVersion: number, reason = "other") =>
    apiRequest<Plan>(`/plans/${planId}/blocks/${blockId}/skip`, {
      method: "POST",
      body: JSON.stringify({ expected_version: expectedVersion, reason })
    }),
  cancelPlanBlockPlacement: (planId: string, blockId: string, expectedVersion: number) =>
    apiRequest<Plan>(`/plans/${planId}/blocks/${blockId}/cancel`, {
      method: "POST",
      body: JSON.stringify({ expected_version: expectedVersion, note: "Removed from Calendar for replanning." })
    }),
  evaluateDay: () =>
    apiRequest<ControlStatus>("/day/evaluate", {
      method: "POST",
      body: JSON.stringify({})
    }),
  replanDay: () =>
    apiRequest<ReplanResponse>("/plans/replan", {
      method: "POST",
      body: JSON.stringify({ reason: "USER_REQUESTED", force: true })
    }),
  explainPlanBlock: (planId: string, blockId: string) =>
    apiRequest<{ plan_id: string; plan_block_id: string; title: string; variant_type?: string | null; factors: DecisionFactor[]; summary: string[] }>(`/plans/${planId}/blocks/${blockId}/explain`),
  listAssistantThreads: () => apiRequest<ConversationThread[]>("/assistant/threads"),
  getAssistantThread: (threadId: string) => apiRequest<ConversationThreadDetail>(`/assistant/threads/${threadId}`),
  createAssistantThread: (payload: { title?: string; default_skill?: string } = {}) =>
    apiRequest<ConversationThread>("/assistant/threads", {
      method: "POST",
      body: JSON.stringify({ default_skill: "self-core", ...payload })
    }),
  archiveAssistantThread: (threadId: string) =>
    apiRequest<ConversationThread>(`/assistant/threads/${threadId}/archive`, { method: "POST" }),
  assistantMessage: (payload: { message: string; role?: AssistantRole; thread_id?: string | null; recent_messages?: Array<Record<string, string>> }) =>
    apiRequest<AssistantResponse>("/assistant/message", {
      method: "POST",
      body: JSON.stringify({
        role: payload.role ?? "GENERAL_ASSISTANT",
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "Europe/Berlin",
        thread_id: payload.thread_id ?? null,
        recent_messages: payload.recent_messages ?? [],
        message: payload.message
      })
    }),
  assistantMessageStream: async (payload: { message: string; role?: AssistantRole; thread_id?: string | null; recent_messages?: Array<Record<string, string>> }, onActivity: (activity: AgentWorkActivity) => void) => {
    const token = await getValidAuthToken();
    const response = await fetch(`${API_BASE_URL}/api/v1/assistant/message/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      body: JSON.stringify({ role: payload.role ?? "GENERAL_ASSISTANT", timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "Europe/Berlin", thread_id: payload.thread_id ?? null, recent_messages: payload.recent_messages ?? [], message: payload.message })
    });
    if (response.status === 401) { clearAuthToken(); window.dispatchEvent(new Event("life-os:auth-expired")); }
    if (!response.ok || !response.body) throw new Error(`Assistant stream failed: ${response.status}`);
    return consumeAssistantStream(response.body, onActivity);
  },
  morningBriefing: () =>
    apiRequest<MorningBriefing>(`/self-core/morning?timezone=${encodeURIComponent(Intl.DateTimeFormat().resolvedOptions().timeZone || "Europe/Berlin")}`, { method: "POST" }),
  foregroundWorkspace: () => apiRequest<ActiveWorkspace | null>("/workspaces/foreground"),
  resumeWorkspace: (workspaceId: string) => apiRequest<ActiveWorkspace>(`/workspaces/${workspaceId}/resume`, { method: "POST" }),
  pendingAssistantProposals: () => apiRequest<AssistantActionProposal[]>("/assistant/proposals/pending"),
  confirmAssistantProposal: (proposalId: string) =>
    apiRequest<AssistantResponse>(`/assistant/proposals/${proposalId}/confirm`, {
      method: "POST"
    }),
  cancelAssistantProposal: (proposalId: string) =>
    apiRequest<AssistantResponse>(`/assistant/proposals/${proposalId}/cancel`, {
      method: "POST"
    }),
  getFeedbackSession: (sessionId: string) =>
    apiRequest<FeedbackSessionState>(`/feedback/sessions/${sessionId}`),
  submitFeedbackClarification: (sessionId: string, answer: string) =>
    apiRequest<FeedbackSessionState>(`/feedback/sessions/${sessionId}/clarification`, {
      method: "POST",
      body: JSON.stringify({ answer })
    }),
  submitFeedbackResponse: (
    sessionId: string,
    payload: {
      question_id: string;
      question_version: number;
      score?: number | null;
      is_skipped: boolean;
      feedback_scope?: string;
      feedback_confidence?: string;
      explanation?: string | null;
    }
  ) =>
    apiRequest<FeedbackSessionState>(`/feedback/sessions/${sessionId}/responses`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  completeFeedback: (sessionId: string) =>
    apiRequest<FeedbackSessionState>(`/feedback/sessions/${sessionId}/complete`, { method: "POST" }),
  cancelFeedback: (sessionId: string) =>
    apiRequest<FeedbackSessionState>(`/feedback/sessions/${sessionId}/cancel`, { method: "POST" }),
  createPushSubscription: (payload: { endpoint: string; keys: { p256dh: string; auth: string }; device_label?: string | null }) =>
    apiRequest<PushSubscriptionRead>("/push/subscriptions", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  createTestNotification: (payload: { title?: string; body?: string; dedupe_key?: string; expires_in_minutes?: number }) =>
    apiRequest<unknown>("/notifications/test", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  exportData: () => apiRequest<Record<string, unknown>>("/export")
  , leisureTrajectory: () => apiRequest<LeisureTrajectory>("/leisure/trajectory")
  , updateLeisureTrajectory: (payload: { target_min: number; target_max: number; week_starts_on?: number; status?: string }) =>
    apiRequest<LeisureTrajectory>("/leisure/trajectory", { method: "PUT", body: JSON.stringify(payload) })
  , movies: (query = "") => apiRequest<Movie[]>(`/movies${query ? `?q=${encodeURIComponent(query)}` : ""}`)
  , createMovie: (payload: { title: string; release_year?: number | null; runtime_minutes?: number | null; genres?: string[] }) =>
    apiRequest<Movie>("/movies", { method: "POST", body: JSON.stringify(payload) })
  , movieWatchlist: () => apiRequest<MovieWatchlistItem[]>("/movies/watchlist")
  , addMovieToWatchlist: (movieId: string) => apiRequest<MovieWatchlistItem>("/movies/watchlist", { method: "POST", body: JSON.stringify({ movie_id: movieId }) })
  , removeMovieFromWatchlist: (itemId: string) => apiRequest<MovieWatchlistItem>(`/movies/watchlist/${itemId}`, { method: "DELETE" })
  , movieHistory: () => apiRequest<MovieViewing[]>("/movies/history")
  , markMovieWatched: (payload: { movie_id: string; watched_at: string; rating?: number | null; notes?: string | null }) =>
    apiRequest<MovieViewing>("/movies/history", { method: "POST", headers: { "Idempotency-Key": crypto.randomUUID() }, body: JSON.stringify(payload) })
  , recommendMovies: (payload: { available_minutes?: number; preferred_genres?: string[]; mood?: string; watchlist_only?: boolean; include_rewatches?: boolean; limit?: number }) =>
    apiRequest<MovieRecommendation>("/movies/recommendations", { method: "POST", body: JSON.stringify(payload) })
  , recordMovieOutcome: (recommendationId: string, optionId: string, outcome: "SELECTED" | "WATCHED" | "REJECTED") =>
    apiRequest(`/movies/recommendations/${recommendationId}/outcomes`, { method: "POST", body: JSON.stringify({ option_id: optionId, outcome, idempotency_key: crypto.randomUUID() }) })
  , previewLetterboxdImport: (payload: { file_name: string; content: string; source_kind?: string }) =>
    apiRequest<MovieImportBatch>("/movies/imports/letterboxd/preview", { method: "POST", body: JSON.stringify(payload) })
  , confirmMovieImport: (batchId: string) => apiRequest<MovieImportBatch>(`/movies/imports/${batchId}/confirm`, { method: "POST" })
  , resolveMovieImportRow: (rowId: string, movieId: string) => apiRequest(`/movies/imports/rows/${rowId}/resolve/${movieId}`, { method: "POST" })
  , socialTrajectory: () => apiRequest<SocialTrajectory>("/social/trajectory")
  , updateSocialTrajectory: (payload: { enabled: boolean; target_min: number; target_max: number; week_starts_on?: number }) =>
    apiRequest<SocialTrajectory>("/social/trajectory", { method: "PUT", body: JSON.stringify(payload) })
  , socialActivities: () => apiRequest<SocialActivity[]>("/social/activities")
  , addSocialActivity: (payload: { activity_type: string; title: string; occurred_at: string; meaningful?: boolean; idempotency_key?: string }) =>
    apiRequest<SocialActivity>("/social/activities", { method: "POST", body: JSON.stringify(payload) })
  , opportunities: (params: { category?: string; relevant?: boolean; starts_after?: string } = {}) => {
    const search = new URLSearchParams();
    if (params.category) search.set("category", params.category);
    if (params.relevant != null) search.set("relevant", String(params.relevant));
    if (params.starts_after) search.set("starts_after", params.starts_after);
    return apiRequest<Opportunity[]>(`/opportunities${search.size ? `?${search}` : ""}`);
  }
  , recommendOpportunities: () => apiRequest<OpportunityRecommendation | null>("/opportunities/recommendations", { method: "POST" })
  , dismissOpportunity: (id: string) => apiRequest<Opportunity>(`/opportunities/${id}/dismiss`, { method: "POST" })
  , recordOpportunityOutcome: (payload: { recommendation_id: string; option_id: string; outcome: "VIEWED" | "SELECTED" | "REJECTED" | "EXECUTED" | "FEEDBACK"; idempotency_key?: string }) =>
    apiRequest("/opportunities/recommendations/outcomes", { method: "POST", body: JSON.stringify(payload) })
  , opportunitySources: () => apiRequest<OpportunitySource[]>("/opportunity-sources")
  , updateOpportunitySource: (sourceId: string, payload: { enabled: boolean; city?: string | null; region?: string | null; country_code?: string | null; categories?: string[]; cadence_minutes?: number; horizon_days?: number }) =>
    apiRequest<OpportunitySource>(`/opportunity-sources/${sourceId}`, { method: "PUT", body: JSON.stringify(payload) })
  , discoverOpportunities: (sourceId: string) => apiRequest(`/opportunity-sources/${sourceId}/discover`, { method: "POST" })
  , quickCapture: (text: string) => apiRequest<QuickCapture>("/quick-capture", {
    method: "POST", headers: { "Idempotency-Key": crypto.randomUUID() },
    body: JSON.stringify({ text, timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "Europe/Berlin" })
  })
  , applyQuickCapture: (captureId: string, version: number, editedPayload: Record<string, unknown> = {}) =>
    apiRequest<QuickCapture>(`/quick-capture/${captureId}/apply`, { method: "POST", body: JSON.stringify({ expected_version: version, edited_payload: editedPayload }) })
  , rejectQuickCapture: (captureId: string) => apiRequest<QuickCapture>(`/quick-capture/${captureId}/reject`, { method: "POST" })
  , reviewItems: () => apiRequest<ReviewItem[]>("/review?status=PENDING")
  , resolveReviewItem: (itemId: string, action: "ACCEPT" | "EDIT_AND_ACCEPT" | "REJECT" | "DISMISS", version: number, editedValues: Record<string, unknown> = {}) =>
    apiRequest<{ item: ReviewItem; canonical_entity_type?: string | null; canonical_entity_id?: string | null; world_revision: number }>(`/review/${itemId}/resolve`, {
      method: "POST", body: JSON.stringify({ action, expected_version: version, edited_values: editedValues })
    })
  , intelligenceSettings: () => apiRequest<IntelligenceControlSurface>("/settings/intelligence")
  , updateIntelligenceSettings: (payload: Partial<IntelligenceSettings> & { expected_version?: number }) =>
    apiRequest<IntelligenceSettings>("/settings/intelligence", { method: "PATCH", body: JSON.stringify(payload) })
  , saveProviderCredential: (provider: "openai" | "gemini" | "jev", apiKey: string) =>
    apiRequest<{ provider: "openai" | "gemini" | "jev"; configured: boolean }>(`/settings/intelligence/providers/${provider}/credential`, { method: "PUT", body: JSON.stringify({ api_key: apiKey }) })
  , deleteProviderCredential: (provider: "openai" | "gemini" | "jev") =>
    apiRequest<{ provider: "openai" | "gemini" | "jev"; configured: boolean }>(`/settings/intelligence/providers/${provider}/credential`, { method: "DELETE" })
  , providerModels: (provider: "openai" | "gemini") =>
    apiRequest<{ provider: "openai" | "gemini"; models: string[] }>(`/settings/intelligence/providers/${provider}/models`)
  , testOpenAIChat: () => apiRequest<OpenAIChatTest>("/settings/intelligence/providers/openai/test", { method: "POST" })
  , testJevDecision: () => apiRequest<JevDecisionTest>("/settings/intelligence/providers/jev/test", { method: "POST" })
  , embeddingSettings: () => apiRequest<EmbeddingSettings>("/settings/intelligence/embeddings")
  , updateEmbeddingSettings: (payload: { provider: "default" | "openai" | "gemini"; model?: string | null; expected_version?: number }) =>
    apiRequest<EmbeddingSettings>("/settings/intelligence/embeddings", { method: "PATCH", body: JSON.stringify(payload) })
  , testEmbeddingProvider: (payload: { provider: "openai" | "gemini"; model?: string }) =>
    apiRequest<EmbeddingConnectionTest>("/settings/intelligence/embeddings/test", { method: "POST", body: JSON.stringify(payload) })
  , updateAgentModels: (agents: Record<string, { provider: "openai" | "gemini"; economy_model: string; fast_model: string; reasoning_model: string }>) =>
    apiRequest<AgentSettings[]>("/settings/intelligence/agents", { method: "PATCH", body: JSON.stringify({ agents }) })
  , updateAgentProfile: (skillName: string, profile: AgentProfile, expected_version?: number) =>
    apiRequest<AgentSettings>(`/settings/intelligence/agents/${encodeURIComponent(skillName)}/profile`, { method: "PATCH", body: JSON.stringify({ ...profile, ...(expected_version == null ? {} : { expected_version }) }) })
};
