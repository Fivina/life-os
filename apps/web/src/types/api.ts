export type StateObservation = {
  id: string;
  observation_type: string;
  value: number;
  observed_at: string;
  source: string;
  notes?: string | null;
};

export type LatestState = {
  values: Record<string, StateObservation>;
  check_in: {
    energy?: number | null;
    mental_state?: number | null;
    observed_at?: string | null;
    observation_ids: Record<string, string>;
  } | null;
  world_revision: number;
};

export type StateObservationBatch = {
  observations: StateObservation[];
  world_revision: number;
};

export type BodyMeasurement = {
  id: string;
  measured_at: string;
  body_weight_kg?: number | null;
  body_fat_percentage?: number | null;
  lean_mass_kg?: number | null;
  muscle_mass_kg?: number | null;
  body_water_percentage?: number | null;
  visceral_fat_rating?: number | null;
  bmi?: number | null;
  source: string;
  metadata_json?: Record<string, unknown>;
  notes?: string | null;
  version: number;
};

export type TrendMetric = {
  latest: number | null;
  rolling_average: number | null;
  sample_count: number;
  window_days: number;
  change: number | null;
  direction: string;
  label: string;
};

export type BodyTrend = {
  latest_measurement: BodyMeasurement | null;
  weight: TrendMetric;
  body_fat: TrendMetric;
};

export type FitnessGoal = {
  id: string;
  target_weight_kg?: number | null;
  target_body_fat_percentage?: number | null;
  target_lean_mass_kg?: number | null;
  direction: string;
  active: boolean;
  notes?: string | null;
  version: number;
};

export type WorkoutProgram = {
  id: string;
  name: string;
  description?: string | null;
  goal_type?: string | null;
  status: string;
  active: boolean;
  version: number;
};

export type Exercise = {
  id: string;
  name: string;
  category?: string | null;
  primary_muscle_group?: string | null;
  equipment?: string | null;
  default_rest_seconds: number;
  active: boolean;
  notes?: string | null;
  version: number;
};

export type WorkoutTemplateExercise = {
  id: string;
  template_id: string;
  exercise_id: string;
  exercise?: Exercise | null;
  order_index: number;
  target_sets: number;
  target_rep_min: number;
  target_rep_max: number;
  target_load_kg?: number | null;
  target_rpe?: number | null;
  rest_seconds: number;
  progression_rule: string;
  load_increment_kg: number;
  notes?: string | null;
  version: number;
};

export type WorkoutTemplate = {
  id: string;
  program_id: string;
  name: string;
  sequence_order: number;
  estimated_duration_minutes: number;
  active: boolean;
  notes?: string | null;
  exercises: WorkoutTemplateExercise[];
  version: number;
};

export type ExerciseSet = {
  id: string;
  workout_session_id?: string | null;
  exercise_id?: string | null;
  template_exercise_id?: string | null;
  sequence: number;
  reps?: number | null;
  load_kg?: number | null;
  rpe?: number | null;
  set_type: string;
  completed_at?: string | null;
  note?: string | null;
  completed: boolean;
  version: number;
};

export type ProgressionState = {
  id: string;
  template_exercise_id: string;
  exercise_id: string;
  rule: string;
  previous_load_kg?: number | null;
  recommended_load_kg?: number | null;
  recommendation: string;
  explanation_json: Record<string, unknown>;
  version: number;
};

export type WorkoutSession = {
  id: string;
  workout_template_id?: string | null;
  source_action_id?: string | null;
  source_plan_block_id?: string | null;
  started_at: string;
  completed_at?: string | null;
  status: string;
  perceived_session_difficulty?: number | null;
  notes?: string | null;
  planned_snapshot_json?: Record<string, unknown>;
  actual_duration_minutes?: number | null;
  modified?: boolean;
  template?: WorkoutTemplate | null;
  sets: ExerciseSet[];
  progression: ProgressionState[];
  version: number;
};

export type RecoveryObservation = {
  id: string;
  observed_at: string;
  soreness?: number | null;
  sleep_quality?: number | null;
  stress?: number | null;
  readiness?: number | null;
  source: string;
  notes?: string | null;
  version: number;
};

export type ReadinessSummary = {
  score: number;
  band: string;
  factors: Array<Record<string, unknown>>;
  latest_observation?: RecoveryObservation | null;
};

export type FitnessCandidate = {
  candidate_id: string;
  title: string;
  template_id: string;
  duration_minutes: number;
  minimum_minutes: number;
  maximum_minutes: number;
  physical_load: number;
  activation_difficulty: number;
  trajectory_value: number;
  expected_state_effect: Record<string, unknown>;
  metadata: Record<string, unknown>;
};

export type FitnessStatus = {
  active_program: WorkoutProgram | null;
  next_workout: WorkoutTemplate | null;
  active_session: WorkoutSession | null;
  latest_measurement: BodyMeasurement | null;
  body_trend: BodyTrend;
  readiness: ReadinessSummary;
  workouts_this_week: number;
  weekly_target: number;
  progression: ProgressionState[];
  candidates: FitnessCandidate[];
  recent_workouts?: WorkoutSession[];
  current_fitness_plan_window?: Array<Record<string, unknown>>;
};

export type Course = {
  id: string;
  name: string;
  code?: string | null;
  description?: string | null;
  institution?: string | null;
  status: string;
  version: number;
};

export type StudyTopic = {
  id: string;
  exam_id: string;
  title: string;
  order_index: number;
  importance_weight: number;
  estimated_required_minutes?: number | null;
  prerequisite_topic_id?: string | null;
  completed_minutes: number;
  status: string;
  version: number;
};

export type LearningTrajectory = {
  exam_id: string;
  strategy_version: string;
  target_preparation_minutes: number;
  raw_completed_minutes: number;
  quality_adjusted_completed_minutes: number;
  remaining_quality_adjusted_minutes: number;
  days_remaining: number;
  hours_remaining: number;
  future_capacity_minutes: number;
  required_daily_minutes: number;
  required_weekly_hours: number;
  load_ratio?: number | null;
  risk: string;
  feasible: boolean;
  shortfall_minutes: number;
  shortfall_hours: number;
  readiness_score: number;
  readiness_label: string;
  topic_coverage_ratio?: number | null;
  latest_safe_start?: string | null;
  behind_safe_pace: boolean;
  calculation_notes: Record<string, unknown>;
};

export type Exam = {
  id: string;
  course_id?: string | null;
  title: string;
  exam_date?: string | null;
  exam_at?: string | null;
  estimated_required_hours: number;
  completed_hours: number;
  target_preparation_minutes: number;
  minimum_required_preparation_minutes?: number | null;
  target_quality_adjusted_minutes?: number | null;
  strategy_version: string;
  importance: string;
  attempts_remaining?: number | null;
  final_attempt: boolean;
  exam_format?: string | null;
  location?: string | null;
  notes?: string | null;
  status: string;
  version: number;
  course?: Course | null;
  topics: StudyTopic[];
  trajectory?: LearningTrajectory | null;
};

export type StudySession = {
  id: string;
  course_id?: string | null;
  exam_id?: string | null;
  topic_id?: string | null;
  source_action_id?: string | null;
  source_plan_block_id?: string | null;
  occurred_at: string;
  started_at: string;
  completed_at?: string | null;
  duration_minutes: number;
  planned_duration_minutes?: number | null;
  completion_status?: string;
  location?: string | null;
  context_json?: Record<string, unknown>;
  quality_rating?: number | null;
  quality_multiplier: number;
  quality_adjusted_minutes: number;
  source: string;
  notes?: string | null;
  version: number;
};

export type LearningCandidate = {
  candidate_id: string;
  title: string;
  exam_id: string;
  course_id?: string | null;
  topic_id?: string | null;
  duration_minutes: number;
  minimum_minutes: number;
  maximum_minutes: number;
  variant: string;
  commitment_level: string;
  cognitive_load: number;
  activation_difficulty: number;
  trajectory_value: number;
  urgency: number;
  neglect_cost: number;
  deadline?: string | null;
  prerequisite_satisfied: boolean;
  expected_state_effect: Record<string, unknown>;
  metadata: Record<string, unknown>;
};

export type LearningStatus = {
  courses: Course[];
  exams: Exam[];
  active_exam: Exam | null;
  candidates: LearningCandidate[];
  recent_sessions: StudySession[];
  current_learning_plan_window: Array<Record<string, unknown>>;
};

export type InventoryItem = {
  id: string;
  ingredient_name: string;
  quantity: number;
  unit: string;
  expires_on?: string | null;
  source: string;
  category?: string | null;
  canonical_unit: string;
  default_storage_location?: string | null;
  is_staple: boolean;
  restock_threshold?: number | null;
  restock_target?: number | null;
  active: boolean;
  notes?: string | null;
  total_quantity: number;
  expiry_status: string;
  lots: InventoryLot[];
  version: number;
};

export type InventoryLot = {
  id: string;
  inventory_item_id: string;
  quantity: number;
  unit: string;
  purchased_at?: string | null;
  expires_at?: string | null;
  storage_location?: string | null;
  source: string;
  status: string;
  version: number;
};

export type RecipeIngredient = {
  id: string;
  recipe_id: string;
  inventory_item_id?: string | null;
  ingredient_name: string;
  quantity: number;
  unit: string;
  optional: boolean;
  substitution_group?: string | null;
  order_index: number;
  version: number;
};

export type Recipe = {
  id: string;
  name: string;
  description?: string | null;
  preparation_minutes: number;
  cooking_minutes: number;
  servings: number;
  calories_per_serving: number;
  protein_g_per_serving: number;
  carbs_g_per_serving?: number | null;
  fat_g_per_serving?: number | null;
  protein_family?: string | null;
  difficulty: string;
  tags: string[];
  steps?: string[];
  techniques?: Array<Record<string, unknown>>;
  active: boolean;
  notes?: string | null;
  ingredients: RecipeIngredient[];
  version: number;
};

export type NutritionTarget = {
  id: string;
  calories_target: number;
  protein_g_target: number;
  source: string;
  effective_from: string;
  effective_to?: string | null;
  status: string;
  notes?: string | null;
  version: number;
};

export type NutritionProgress = {
  date: string;
  calories_target?: number | null;
  protein_g_target?: number | null;
  calories_consumed: number;
  protein_g_consumed: number;
  calories_remaining?: number | null;
  protein_g_remaining?: number | null;
  calories_over_target: number;
  protein_g_over_target: number;
};

export type MealHistory = {
  id: string;
  recipe_id?: string | null;
  name_snapshot: string;
  consumed_at: string;
  servings: number;
  calories_snapshot: number;
  protein_g_snapshot: number;
  carbs_g_snapshot?: number | null;
  fat_g_snapshot?: number | null;
  satisfaction?: number | null;
  source: string;
  source_plan_block_id?: string | null;
  notes?: string | null;
  version: number;
};

export type MealRecommendation = {
  recommendation_id?: string | null;
  option_id?: string | null;
  recipe: Recipe;
  score: number;
  score_factors: Record<string, number>;
  explanation: string[];
  availability: string;
  missing_ingredients: string[];
  expiring_ingredients_used: string[];
  estimated_missing_cost?: number | null;
  budget_state?: string;
  technique_opportunities?: string[];
};

export type ChefRecommendationSet = { recommendation_id: string; options: MealRecommendation[] };

export type MealIntent = {
  version: "meal-intent-v1";
  meal_type?: "BREAKFAST" | "LUNCH" | "DINNER" | "SNACK" | null;
  cuisine_preferences: string[];
  styles: string[];
  protein_preferences: string[];
  ingredient_preferences: string[];
  ingredient_exclusions: string[];
  dietary_constraints: string[];
  max_total_minutes?: number | null;
  max_active_minutes?: number | null;
  servings: number;
  protein_priority: "NORMAL" | "HIGH";
  heaviness_preference?: string | null;
  inventory_preference: "USE_WHAT_I_HAVE" | "MINIMAL_SHOPPING" | "SHOPPING_ALLOWED";
  confidence: number;
  ambiguities: string[];
  free_text_source: string;
};

export type ChefMealOption = {
  recommendation_id?: string | null;
  option_id?: string | null;
  recipe: Recipe;
  score: number;
  score_factors: Record<string, number>;
  reason_codes: string[];
  why_it_fits: string;
  total_minutes: number;
  active_minutes: number;
  nutrition: { calories?: number | null; protein_g?: number | null; carbs_g?: number | null; fat_g?: number | null; source?: string };
  nutrition_confidence: "COMPLETE" | "PARTIAL" | "UNKNOWN";
  inventory_status: "FULLY_IN_STOCK" | "MOSTLY_IN_STOCK" | "SHOPPING_REQUIRED" | "INFEASIBLE";
  ingredient_requirements: Array<{ ingredient_name: string; required_quantity: number; available_quantity: number; missing_quantity: number; unit: string; expiring_soon: boolean }>;
  missing_ingredients: string[];
  expiring_ingredients_used: string[];
  estimated_grocery_delta?: number | null;
  grocery_currency?: string | null;
  budget_status: string;
  technique_opportunities: string[];
};

export type ChefIntentRecommendation = {
  intent: MealIntent;
  interpretation_mode: "AI" | "DETERMINISTIC_FALLBACK" | "EXPLICIT";
  interpretation_warning?: string | null;
  recommendation_id?: string | null;
  options: ChefMealOption[];
  response_text: string;
};

export type ActiveWorkspace = {
  id: string;
  workspace_type: string;
  status: string;
  is_foreground: boolean;
  current_step?: string | null;
  payload: Record<string, unknown>;
  state_revision: number;
};

export type SelfCoreReference = {
  ref_type: string;
  ref_id: string;
  title: string;
  status?: string | null;
  starts_at?: string | null;
  detail?: string | null;
};

export type MorningBriefing = {
  context: {
    date: string;
    generated_at: string;
    fingerprint: string;
    plan_id: string;
    plan_version: number;
    world_revision: number;
    first_block?: SelfCoreReference | null;
    important_blocks: SelfCoreReference[];
    protected_commitments: SelfCoreReference[];
    trajectory_changes: SelfCoreReference[];
    active_proposals: SelfCoreReference[];
    attention_items: SelfCoreReference[];
    active_workspace?: SelfCoreReference | null;
    kitchen_signals: SelfCoreReference[];
    finance_signal?: Record<string, unknown> | null;
    omitted_categories: string[];
    source_refs: string[];
    briefing_policy_version: string;
  };
  message: string;
  reused: boolean;
  plan_created: boolean;
};

export type MealPlan = {
  id: string;
  recipe_id: string;
  recipe: Recipe;
  recommendation_id?: string | null;
  recommendation_option_id?: string | null;
  planned_for: string;
  meal_type: string;
  status: string;
  planned_servings: number;
  nutrition_snapshot: Record<string, unknown>;
  planned_ingredients: Array<Record<string, unknown>>;
  modifications: Record<string, unknown>;
  shopping_action_id?: string | null;
  cooking_action_id?: string | null;
  meal_history_id?: string | null;
  version: number;
};

export type CookingCompetency = {
  id: string;
  technique_key: string;
  technique_name: string;
  estimated_level: number;
  confidence: number;
  evidence_count: number;
  successful_repetitions: number;
  last_practiced_at?: string | null;
  band: string;
  version: number;
};

export type ShoppingNeedItem = {
  id: string;
  shopping_need_id: string;
  inventory_item_id?: string | null;
  ingredient_name: string;
  quantity: number;
  unit: string;
  satisfied: boolean;
  priority_class?: string;
  reason?: string | null;
  estimated_cost?: number | null;
  purchased_quantity?: number;
  status?: string;
  version: number;
};

export type ShoppingAggregate = {
  ingredient_name: string;
  quantity: number;
  unit: string;
  priority_class: string;
  reasons: string[];
  estimated_cost: number | null;
  source_item_ids: string[];
  status: string;
};

export type MediaAsset = { id: string; kind: string; storage_provider: string; mime_type: string; size_bytes: number; content_hash: string; source: string; version: number };
export type ReceiptLine = {
  id: string; line_number: number; raw_text: string; normalized_name?: string | null; quantity?: number | null; unit?: string | null;
  unit_price?: string | null; line_total?: string | null; category: string; confidence_name: number; confidence_quantity: number;
  confidence_price: number; review_required: boolean; accepted: boolean; version: number;
};
export type ReceiptImport = {
  id: string; asset: MediaAsset; merchant?: string | null; transaction_at?: string | null; currency: string; subtotal?: string | null;
  tax?: string | null; total?: string | null; status: string; confidence: number; failure_reason?: string | null;
  finance_transaction_id?: string | null; confirmed_at?: string | null; review_count: number; lines: ReceiptLine[]; version: number;
};

export type FinanceTransaction = { id: string; occurred_on: string; amount: string; currency: string; direction: string; merchant_name?: string | null; merchant_raw?: string | null; description?: string | null; category_name?: string | null; source: string; version: number };
export type FinanceBudget = { id: string; name: string; category_name?: string | null; amount: string; spent: string; remaining: string; currency: string; month_start: string; protected: boolean; active: boolean; version: number };
export type RecurringExpense = { id: string; name: string; typical_amount: string; currency: string; interval_days: number; next_expected_on?: string | null; confidence: number; evidence_count: number; status: string; version: number };
export type SafeToSpend = { currency: string; income_to_date: string; spending_to_date: string; upcoming_recurring: string; protected_budget_remaining: string; planned_savings: string; safe_to_spend: string; assumptions: string[] };
export type FinanceImportRow = { id: string; row_number: number; occurred_on?: string | null; amount?: string | null; currency: string; direction?: string | null; merchant_raw?: string | null; description?: string | null; category_name?: string | null; confidence: number; review_required: boolean; status: string; error?: string | null; version: number };
export type FinanceImportBatch = { id: string; filename: string; status: string; currency: string; row_count: number; ready_count: number; review_count: number; duplicate_count: number; error_count: number; confirmed_at?: string | null; rows: FinanceImportRow[]; version: number };
export type FinanceOverview = { month_start: string; currency: string; income: string; spending: string; category_totals: Record<string, string>; budgets: FinanceBudget[]; recurring_expenses: RecurringExpense[]; safe_to_spend: SafeToSpend; recent_transactions: FinanceTransaction[]; savings_goals: Array<Record<string, unknown>> };

export type ShoppingNeed = {
  id: string;
  title: string;
  status: string;
  required_by?: string | null;
  reason?: string | null;
  source: string;
  forecast_window_days: number;
  metadata_json: Record<string, unknown>;
  items: ShoppingNeedItem[];
  version: number;
};

export type KitchenStatus = {
  inventory_count: number;
  expiring_lots: number;
  expired_lots: number;
  nutrition: NutritionProgress;
  top_recommendation?: MealRecommendation | null;
  shopping_need_count: number;
  active_candidate_count: number;
};

export type Commitment = {
  id: string;
  title: string;
  description?: string | null;
  level: string;
  commitment_type: string;
  starts_at: string | null;
  ends_at: string | null;
  timezone: string;
  all_day: boolean;
  location?: string | null;
  recurrence: Record<string, unknown>;
  source: string;
  status: string;
  notes?: string | null;
  version: number;
  world_revision?: number | null;
};

export type ActionIntention = {
  id: string;
  title: string;
  domain: string;
  level: string;
  description?: string | null;
  earliest_start?: string | null;
  latest_start?: string | null;
  deadline?: string | null;
  estimated_minutes?: number | null;
  completed_minutes: number;
  duration_min_minutes?: number | null;
  duration_max_minutes?: number | null;
  location?: string | null;
  context?: string | null;
  status: string;
  scheduled_start?: string | null;
  scheduled_end?: string | null;
  metadata_json: Record<string, unknown>;
  requirement_key?: string | null;
  source_entity_type?: string | null;
  source_entity_id?: string | null;
  goal_id?: string | null;
  trajectory_id?: string | null;
  generated_reason?: string | null;
  generation_version?: string;
  planning_priority?: number;
  version: number;
  world_revision?: number | null;
};

export type HouseholdTask = {
  id: string;
  title: string;
  category: string;
  recurrence: Record<string, unknown>;
  estimated_duration_minutes: number;
  minimum_duration_minutes: number;
  location: string;
  priority: number;
  last_completed_at?: string | null;
  next_due_at?: string | null;
  active: boolean;
  notes?: string | null;
  due_status: string;
  version: number;
};

export type HouseholdOverview = {
  due: HouseholdTask[];
  upcoming: HouseholdTask[];
  recently_completed: HouseholdTask[];
  active_count: number;
};

export type GoalTrajectory = {
  id: string;
  goal_id?: string | null;
  name: string;
  metric_name?: string | null;
  target_value?: number | null;
  current_value?: number | null;
  unit?: string | null;
  status: string;
  risk: string;
  on_track?: boolean | null;
  target_date?: string | null;
  current_rate?: number | null;
  required_rate?: number | null;
  metadata_json: Record<string, unknown>;
};

export type Milestone = {
  id: string;
  goal_id: string;
  title: string;
  status: string;
  target_date?: string | null;
  completed_at?: string | null;
  version: number;
};

export type Goal = {
  id: string;
  title: string;
  domain: string;
  description?: string | null;
  status: string;
  priority: number;
  target_date?: string | null;
  success_condition?: string | null;
  progress_mode: string;
  manual_progress?: number | null;
  active: boolean;
  progress?: number | null;
  trajectory?: GoalTrajectory | null;
  milestones: Milestone[];
  linked_upcoming_actions: Array<Record<string, unknown>>;
  version: number;
};

export type GoalsOverview = {
  goals: Goal[];
  weekly_focus: Array<{ id: string; week_start: string; goal_id?: string | null; title: string; priority_boost: number; active: boolean; version: number }>;
};

export type CalendarProjection = {
  commitments: Array<{
    canonical_id: string;
    canonical_type: "commitment";
    title: string;
    starts_at: string;
    ends_at: string;
    status: string;
    level: string;
    commitment_type: string;
    location?: string | null;
    source: string;
    version: number;
  }>;
  planning_pool: ActionIntention[];
  world_revision: number;
  current_plan?: Plan | null;
};

export type DecisionFactor = {
  factor: string;
  contribution: number;
  notes?: string | null;
};

export type PlanBlock = {
  id: string;
  source_type: string;
  source_id?: string | null;
  action_id?: string | null;
  commitment_id?: string | null;
  domain?: string | null;
  title: string;
  starts_at: string;
  ends_at: string;
  duration_minutes: number;
  block_type: "hard_commitment" | "generated_action" | "slack" | string;
  commitment_level?: string | null;
  movable: boolean;
  status: string;
  started_at?: string | null;
  finished_at?: string | null;
  actual_duration_minutes?: number | null;
  outcome_reason?: string | null;
  note?: string | null;
  action_group_id?: string | null;
  variant_type?: string | null;
  frozen_until?: string | null;
  user_locked?: boolean;
  user_modified?: boolean;
  original_starts_at?: string | null;
  residual_minutes?: number;
  decision_factors: DecisionFactor[];
  version: number;
};

export type PlanSummary = {
  flexible_work_minutes: number;
  hard_commitment_minutes: number;
  slack_minutes: number;
  actions_scheduled: number;
  actions_unscheduled: number;
  planning_load: string;
  stress_estimate: number;
  stress_threshold: number;
  state_band: string;
  usable_flexible_minutes: number;
  required_slack_minutes: number;
};

export type UnscheduledAction = {
  source_action_id: string;
  title: string;
  reason: string;
  score: number;
  required_minutes?: number;
  available_minutes?: number;
  shortfall_minutes?: number;
  risk_status?: string;
};

export type Plan = {
  id: string;
  user_id: string;
  planner_version: string;
  generated_from_world_revision?: number | null;
  status: string;
  planning_day?: string | null;
  horizon_start?: string | null;
  horizon_end?: string | null;
  generated_at: string;
  previous_plan_id?: string | null;
  replan_reason?: string | null;
  control_loop_version: string;
  plan_diff: PlanDiff | null;
  last_evaluated_at?: string | null;
  last_replanned_at?: string | null;
  summary_metrics: PlanSummary;
  decision_factors: DecisionFactor[];
  personal_model_snapshot?: PersonalModelSnapshot | null;
  personal_model_revision?: number;
  overload_status?: string;
  shortfall_minutes?: number;
  overload?: Record<string, unknown>;
  blocks: PlanBlock[];
  unscheduled_actions: UnscheduledAction[];
  current_world_revision?: number | null;
  version: number;
};

export type PlanProposal = {
  id: string;
  exam_id: string;
  source_trace_id?: string | null;
  parent_proposal_id?: string | null;
  current_plan_id: string;
  current_plan_version: number;
  current_world_revision: number;
  applied_plan_id?: string | null;
  trigger: string;
  reason_code: string;
  trajectory_snapshot: Record<string, unknown>;
  deviation: Record<string, unknown>;
  candidate_plan: Record<string, unknown>;
  changes: Array<Record<string, unknown>>;
  expected_effects: {
    scheduled_minutes?: { current: number; proposed: number; delta: number };
    projected_shortfall_minutes?: { current: number; proposed: number };
    scheduled_coverage?: { current: number; proposed: number };
    protected_blocks_changed?: number;
    exam_allocation_effects?: Array<{ exam_id: string; current_minutes: number; proposed_minutes: number; delta_minutes: number }>;
  };
  tradeoffs: Array<Record<string, unknown>>;
  confidence: Record<string, number | null>;
  modification: Record<string, unknown>;
  authority_level: number;
  attention_action: string;
  status: "DRAFT" | "PRESENTED" | "ACCEPTED" | "MODIFIED" | "REJECTED" | "EXPIRED" | "APPLY_FAILED";
  expires_at: string;
  presented_at?: string | null;
  accepted_at?: string | null;
  modified_at?: string | null;
  rejected_at?: string | null;
  expired_at?: string | null;
  policy_version: string;
  planner_version: string;
  calculation_version: string;
  created_at: string;
  updated_at: string;
  version: number;
};

export type PlanningAllocation = {
  id: string;
  planning_date: string;
  action_group_id: string;
  source_action_id?: string | null;
  domain: string;
  required_minutes: number;
  allocated_minutes: number;
  completed_minutes: number;
  debt_minutes: number;
  deadline?: string | null;
  status: string;
  risk_status: string;
  reason_json: Record<string, unknown>;
};

export type HorizonAllocation = {
  horizon_start: string;
  horizon_end: string;
  status: string;
  required_minutes: number;
  available_minutes: number;
  shortfall_minutes: number;
  allocations: PlanningAllocation[];
};

export type PersonalModelSnapshot = {
  status: string;
  feature_schema_version: string;
  model_revision: number;
  active_model_ids: Record<string, string>;
  model_versions: Record<string, number>;
  parameters: Record<string, unknown>;
  confidence: Record<string, number>;
  evidence_counts: Record<string, number>;
  fallback_reasons: Record<string, string>;
};

export type PersonalModelRefresh = {
  id: string;
  status: string;
  started_at: string;
  finished_at?: string | null;
  feature_schema_version: string;
  extraction_version: string;
  evidence_n: number;
  metrics_json: Record<string, unknown>;
  error?: string | null;
  version: number;
};

export type PersonalModelSummary = {
  feature_schema_version: string;
  extraction_version: string;
  status: string;
  evidence_n: number;
  active_model_count: number;
  candidate_model_count: number;
  rejected_model_count: number;
  pattern_count: number;
  corrected_pattern_count: number;
  fallback_rate: number;
  latest_refresh?: PersonalModelRefresh | null;
  snapshot: PersonalModelSnapshot;
  metrics: Record<string, unknown>;
};

export type PersonalModelVersion = {
  id: string;
  model_type: string;
  model_stage: string;
  version: number;
  feature_schema_version: string;
  status: string;
  parameters: Record<string, unknown>;
  evidence_start?: string | null;
  evidence_end?: string | null;
  evidence_n: number;
  effective_evidence_n: number;
  confidence: number;
  metrics: Record<string, unknown>;
  baseline_metrics: Record<string, unknown>;
  promotion_reason?: string | null;
  promoted_at?: string | null;
  supersedes_model_version_id?: string | null;
  refresh_run_id?: string | null;
};

export type PatternEvidence = {
  id: string;
  pattern_type: string;
  scope: Record<string, unknown>;
  claim: string;
  evidence_n: number;
  weighted_support: number;
  confidence: number;
  first_observed?: string | null;
  last_observed?: string | null;
  last_updated: string;
  status: string;
  correction_metadata: Record<string, unknown>;
  source_model_version_id?: string | null;
  version: number;
};

export type MemoryItem = {
  id: string;
  memory_type: string;
  domain: string;
  content: string;
  normalized_key: string;
  polarity: number;
  confidence: number;
  effective_confidence: number;
  importance: number;
  status: string;
  pinned: boolean;
  user_confirmed: boolean;
  source_kind: string;
  first_observed_at: string;
  last_observed_at: string;
  last_confirmed_at?: string | null;
  valid_from?: string | null;
  valid_until?: string | null;
  supersedes_memory_id?: string | null;
  embedding_provider?: string | null;
  embedding_model?: string | null;
  embedding_dimension?: number | null;
  embedding_version?: string | null;
  created_at: string;
  updated_at: string;
  version: number;
  evidence_count: number;
};

export type MemoryEvidence = {
  id: string;
  source_type: string;
  source_id?: string | null;
  evidence_kind: string;
  direction: string;
  weight: number;
  observed_at: string;
  excerpt?: string | null;
  metadata_json: Record<string, unknown>;
};

export type MemoryDetail = MemoryItem & {
  evidence: MemoryEvidence[];
};

export type PushSubscriptionRead = {
  id: string;
  endpoint: string;
  device_label?: string | null;
  status: string;
  last_success_at?: string | null;
  last_failure_at?: string | null;
  failure_count: number;
  version: number;
};

export type PlanDiff = {
  previous_plan_id?: string | null;
  new_plan_id?: string | null;
  trigger: string;
  kept_block_ids: string[];
  moved_blocks: Array<Record<string, unknown>>;
  shortened_blocks: Array<Record<string, unknown>>;
  removed_blocks: Array<Record<string, unknown>>;
  added_blocks: Array<Record<string, unknown>>;
  deferred_action_ids: string[];
  previous_stress?: number | null;
  new_stress?: number | null;
  previous_slack_minutes?: number | null;
  new_slack_minutes?: number | null;
};

export type ControlStatus = {
  plan: Plan | null;
  control_status: string;
  replan_reason?: string | null;
  last_evaluated_at: string;
  last_replanned_at?: string | null;
  plan_diff?: PlanDiff | null;
};

export type ReplanResponse = {
  plan: Plan | null;
  replan_mode: string;
  trigger_reason: string;
  control_status: string;
  plan_diff: PlanDiff;
  last_evaluated_at: string;
  last_replanned_at?: string | null;
};

export type AssistantRole = "GENERAL_ASSISTANT" | "FITNESS_COACH" | "LEARNING_COACH" | "HOME_MANAGER" | "CHEF" | "FINANCE_ADVISOR";

export type AssistantResponseType = "INFORMATION" | "PROPOSAL" | "CLARIFICATION" | "MUTATION_RESULT" | "NO_ACTION" | "ERROR" | "FEEDBACK";

export type FeedbackDimension =
  | "TIMING"
  | "CONTENT_USEFULNESS"
  | "CONTEXT_SELECTION"
  | "FREQUENCY"
  | "TONE"
  | "PRIORITY"
  | "QUESTION_USEFULNESS"
  | "PLAN_REALISM"
  | "MEMORY_CORRECTNESS"
  | "ACTION_CORRECTNESS"
  | "FACTUAL_ACCURACY"
  | "UI_STATE_MISMATCH"
  | "VOICE_TRANSCRIPTION"
  | "LATENCY";

export type FeedbackQuestion = {
  question_id: string;
  question_version: number;
  dimension: FeedbackDimension;
  prompt: string;
  low_label: string;
  high_label: string;
};

export type FeedbackClarification = {
  question_id: string;
  question_version: number;
  prompt: string;
};

export type FeedbackSessionState = {
  result_code: string;
  session_id?: string | null;
  status?: "ACTIVE" | "COMPLETED" | "CANCELLED" | "EXPIRED" | null;
  parent_conversation_id?: string | null;
  parent_workspace_id?: string | null;
  target_cognitive_trace_id?: string | null;
  current_question_index: number;
  questions_planned_count: number;
  questions_answered_count: number;
  clarification?: FeedbackClarification | null;
  next_question?: FeedbackQuestion | null;
  resume_state: Record<string, unknown>;
};

export type AssistantActionProposal = {
  id: string;
  thread_id?: string | null;
  tool_name: string;
  arguments: Record<string, unknown>;
  summary: string;
  consequence_category: string;
  expected_world_revision?: number | null;
  status: string;
  expires_at: string;
  confirmation_required: boolean;
  version: number;
};

export type AssistantMutationResult = {
  tool_name: string;
  entity_type?: string | null;
  entity_id?: string | null;
  world_revision?: number | null;
  result: Record<string, unknown>;
};

export type AssistantExplanation = {
  title?: string | null;
  factors: Array<Record<string, unknown>>;
  summary: string;
};

export type AssistantResponse = {
  message: string;
  role_used: AssistantRole;
  response_type: AssistantResponseType;
  proposed_action?: AssistantActionProposal | null;
  mutation_result?: AssistantMutationResult | null;
  explanation?: AssistantExplanation | null;
  entity_references: Array<Record<string, unknown>>;
  request_id: string;
  provider?: string | null;
  model?: string | null;
  model_tier: "NO_AI" | "STANDARD" | "STRONG";
  capability?: "ECONOMY" | "FAST" | "REASONING" | "VISION" | "IMAGE" | "EMBEDDING" | null;
  skill_name?: string | null;
  skill_version?: string | null;
  thread_id?: string | null;
  assistant_message_id?: string | null;
  cognitive_trace_ref?: string | null;
  orchestration_route?: string | null;
  error_code?: string | null;
  feedback_session_id?: string | null;
  feedback_status?: string | null;
  feedback_question?: Record<string, unknown> | null;
  work_log?: AgentWorkActivity[];
};

export type AgentWorkActivity = {
  sequence: number;
  kind: "model" | "tool" | "delegation" | "routing";
  skill_name: string;
  tool_name: string | null;
  status: "started" | "completed" | "failed" | "awaiting_confirmation";
};

export type ConversationThread = {
  id: string;
  title: string;
  status: string;
  default_skill: string;
  last_message_at: string;
  created_at: string;
  updated_at: string;
  version: number;
};

export type ConversationMessage = {
  id: string;
  thread_id: string;
  role: "user" | "assistant" | "system";
  content: string;
  skill_name?: string | null;
  request_id?: string | null;
  sequence_number: number;
  metadata_json: Record<string, unknown>;
  created_at: string;
};

export type ConversationThreadDetail = ConversationThread & {
  messages: ConversationMessage[];
  summary?: {
    summary: string;
    covered_message_count: number;
    covers_until_message_id?: string | null;
    updated_at: string;
  } | null;
};

export type NotebookEntry = {
  id: string;
  entry_type: "GENERAL" | "IMPLEMENTATION_IDEA";
  title: string;
  content: string;
  status: "ACTIVE" | "REVIEWED" | "PROMOTED" | "ARCHIVED";
  source: string;
  tags_json: string[];
  reviewed_at?: string | null;
  archived_at?: string | null;
  promoted_at?: string | null;
  embedding_provider?: string | null;
  created_at: string;
  updated_at: string;
  version: number;
};

export type NotebookSearchResult = {
  entry: NotebookEntry;
  score: number;
  lexical_score: number;
  semantic_score?: number | null;
};

export type StandingCalendarRule = {
  id: string;
  name: string;
  rule_type: "SPORTS_FIXTURE";
  enabled: boolean;
  protected: boolean;
  auto_create: boolean;
  source_provider: string;
  source_identity: string;
  source_config_json: Record<string, unknown>;
  sync_interval_days: number;
  last_sync_at?: string | null;
  next_sync_at?: string | null;
  last_sync_status: string;
  last_sync_summary_json: Record<string, unknown>;
  last_error?: string | null;
  version: number;
};

export type FixtureBinding = {
  id: string;
  commitment_id?: string | null;
  source_provider: string;
  source_fixture_id: string;
  fixture_status: string;
  kickoff_at?: string | null;
  suppressed: boolean;
  protection_overridden: boolean;
  normalized_json: Record<string, unknown>;
  version: number;
};

export type FixtureSyncSummary = {
  rule_id: string;
  status: "SUCCESS" | "FAILED" | "SKIPPED";
  fetched: number;
  created: number;
  updated: number;
  cancelled: number;
  noop: number;
  suppressed: number;
  error?: string | null;
};

export type LeisureTrajectory = {
  id: string;
  leisure_type: "MOVIE";
  period: "WEEK";
  target_min: number;
  target_max: number;
  week_starts_on: number;
  status: "ACTIVE" | "PAUSED" | "ARCHIVED";
  period_start: string;
  period_end: string;
  completed_count: number;
  state: "BELOW_RANGE" | "IN_RANGE" | "ABOVE_RANGE" | "PAUSED";
  remaining_to_min: number;
};

export type Movie = {
  id: string;
  title: string;
  original_title?: string | null;
  release_year?: number | null;
  release_date?: string | null;
  runtime_minutes?: number | null;
  genres: string[];
  overview?: string | null;
  poster_url?: string | null;
  metadata_source?: string | null;
  external_ids: Array<{ provider: string; external_id: string; source_url?: string | null }>;
};

export type MovieWatchlistItem = {
  id: string;
  movie_id: string;
  status: "ACTIVE" | "REMOVED" | "WATCHED";
  priority: number;
  source: string;
  source_ref?: string | null;
  notes?: string | null;
  added_at: string;
  movie: Movie;
};

export type MovieViewing = {
  id: string;
  movie_id: string;
  watched_at: string;
  source: string;
  rewatch: boolean;
  rating?: number | null;
  rating_scale?: number | null;
  liked?: boolean | null;
  notes?: string | null;
  recommendation_id?: string | null;
  recommendation_option_id?: string | null;
  movie: Movie;
};

export type MovieRecommendationOption = {
  id: string;
  label: string;
  rank: number;
  score?: number | null;
  payload_json: {
    movie_id: string;
    runtime_minutes?: number | null;
    genres: string[];
    release_year?: number | null;
    poster_url?: string | null;
    score_factors: Record<string, number>;
    explanation: string[];
  };
  reference_type?: string | null;
  reference_id?: string | null;
};

export type MovieRecommendation = {
  id: string;
  domain: string;
  kind: string;
  title: string;
  reason?: string | null;
  context_snapshot: Record<string, unknown>;
  status: string;
  created_at: string;
  options: MovieRecommendationOption[];
};

export type MovieImportRow = {
  id: string;
  source_kind: string;
  source_row_key: string;
  status: "READY" | "REVIEW_REQUIRED" | "ERROR" | "IMPORTED" | "SKIPPED";
  error?: string | null;
  normalized: { title?: string; year?: number; rating?: number; letterboxd_uri?: string };
  movie_id?: string | null;
};

export type MovieImportBatch = {
  id: string;
  provider: string;
  file_name: string;
  status: "PREVIEW" | "CONFIRMED" | "PARTIAL" | "FAILED";
  summary: Record<string, number>;
  confirmed_at?: string | null;
  rows: MovieImportRow[];
};

export type SocialTrajectory = {
  goal_id: string;
  trajectory_id: string;
  enabled: boolean;
  period: "WEEK";
  target_min: number;
  target_max: number;
  week_starts_on: number;
  period_start: string;
  period_end: string;
  completed_count: number;
  state: "BELOW_RANGE" | "IN_RANGE" | "ABOVE_RANGE" | "DISABLED";
  remaining_to_min: number;
  qualification: string;
};

export type Opportunity = {
  id: string;
  opportunity_type: string;
  title: string;
  description?: string | null;
  starts_at: string;
  ends_at?: string | null;
  timezone: string;
  venue?: string | null;
  city?: string | null;
  region?: string | null;
  country_code?: string | null;
  source_url?: string | null;
  cost_min?: string | number | null;
  cost_max?: string | number | null;
  currency?: string | null;
  status: string;
  tags: string[];
  user_status: "AVAILABLE" | "INTERESTED" | "DISMISSED" | "ATTENDED";
  reasons: string[];
  feasibility: { feasible?: boolean; status?: string; reason_codes?: string[]; requires_plan_proposal?: boolean };
};

export type OpportunityRecommendation = {
  id: string;
  domain: string;
  kind: string;
  title: string;
  reason?: string | null;
  options: Array<{
    id: string;
    label: string;
    rank: number;
    score?: number | null;
    reference_id?: string | null;
    payload_json: { opportunity_id: string; reasons: string[]; feasibility: Record<string, unknown> };
  }>;
};

export type OpportunitySource = {
  id: string;
  source_id: string;
  enabled: boolean;
  configured: boolean;
  city?: string | null;
  region?: string | null;
  country_code?: string | null;
  categories: string[];
  cadence_minutes: number;
  horizon_days: number;
  last_discovery_at?: string | null;
  next_discovery_at?: string | null;
  last_status: string;
  last_summary: Record<string, unknown>;
  last_error?: string | null;
};

export type SocialActivity = {
  id: string;
  activity_type: string;
  title: string;
  occurred_at: string;
  meaningful: boolean;
  source: string;
  source_ref?: string | null;
};

export type QuickCapture = {
  id: string;
  schema_version: string;
  raw_text: string;
  status: "PROPOSED" | "PENDING_REVIEW" | "APPLIED" | "REJECTED" | "INVALID" | "DUPLICATE" | "SUPERSEDED";
  interpreted_domain: string;
  intent_type: string;
  target_entity_type?: string | null;
  target_entity_id?: string | null;
  structured_payload: Record<string, unknown>;
  confidence: number;
  ambiguity_flags: string[];
  consequence_level: "LOW" | "MEDIUM" | "HIGH";
  confirmation_required: boolean;
  review_required: boolean;
  policy_outcome: "APPLY" | "REQUEST_CONFIRMATION" | "SEND_TO_REVIEW" | "REJECT_INVALID" | "NOOP_DUPLICATE";
  reason_codes: string[];
  interpreter_provider: string;
  interpreter_model?: string | null;
  review_item_id?: string | null;
  canonical_entity_type?: string | null;
  canonical_entity_id?: string | null;
  expected_world_revision: number;
  created_at: string;
  applied_at?: string | null;
  version: number;
};

export type ReviewItem = {
  id: string;
  review_type: string;
  status: "PENDING" | "RESOLVED" | "DISMISSED" | "EXPIRED" | "SUPERSEDED";
  priority: number;
  source: string;
  source_ref: string;
  summary: string;
  question: string;
  candidate_values: Record<string, unknown>;
  evidence: Record<string, unknown>;
  confidence: number;
  ambiguity_reasons: string[];
  affected_domain: string;
  target_entity_type?: string | null;
  target_entity_id?: string | null;
  resolution: Record<string, unknown>;
  expires_at?: string | null;
  correlation_id?: string | null;
  expected_world_revision?: number | null;
  expected_target_version?: number | null;
  created_at: string;
  updated_at: string;
  resolved_at?: string | null;
  version: number;
};

export type IntelligenceSettings = {
  schema_version: string;
  proactivity_mode: "QUIET" | "BALANCED" | "PROACTIVE";
  memory_visible: boolean;
  patterns_visible: boolean;
  passive_suggestions_enabled: boolean;
  questions_enabled: boolean;
  interruptions_enabled: boolean;
  prospective_resurfacing_enabled: boolean;
  opportunity_suggestions_enabled: boolean;
  monthly_ai_budget_eur?: number | null;
  disabled_skills: string[];
  version: number;
};

export type IntelligenceControlSurface = {
  settings: IntelligenceSettings;
  memory: { visible: boolean; counts: Record<string, number>; controls: string[] };
  patterns: { visible: boolean; counts: Record<string, number>; controls: string[] };
  conversations: { counts: Record<string, number>; controls: string[]; delete_semantics: string };
  skills: Array<{ name: string; description: string; version: string; enabled: boolean; configured_enabled: boolean; capabilities: string[]; roles: string[] }>;
  providers: Array<{ id: string; kind: string; enabled: boolean; configured: boolean; credential_configured?: boolean; credential_source?: string; credential_storage_available?: boolean; state: "available" | "disabled" | "not_configured"; capabilities: string[]; models: string[] }>;
  agents: AgentSettings[];
  active_agent_runtime: "legacy" | "sdk";
  live_agents_enabled: boolean;
  credential_management_available: boolean;
  usage: { monthly_spend_eur: number; budget_eur: number; warning: boolean; economy_only: boolean; optional_suppressed: boolean; by_provider: Record<string, number>; by_model: Record<string, number>; by_capability: Record<string, number>; by_skill: Record<string, number> };
  privacy: { export_endpoint: string; memory_forget_endpoint: string; memory_correct_endpoint: string; conversation_archive_endpoint: string; account_delete_supported: boolean };
};

export type EmbeddingSettings = {
  provider: "default" | "openai" | "gemini";
  model: string;
  effective_provider: string;
  dimensions: number;
  credential_configured: boolean;
  version: number;
};

export type EmbeddingConnectionTest = {
  provider: "openai" | "gemini";
  model: string;
  dimensions: number;
  connected: boolean;
};

export type OpenAIChatTest = {
  provider: "openai";
  model: string;
  connected: boolean;
  passed: boolean;
  response: string;
  latency_ms: number;
};

export type JevDecisionTest = {
  provider: "jev";
  model: string;
  connected: boolean;
  passed: boolean;
  selected_answer: boolean;
  true_probability: number;
  trace_id?: string | null;
  latency_ms: number;
};

export type AgentSettings = {
  skill_name: string;
  name: string;
  description: string;
  roles: string[];
  provider: "openai" | "gemini";
  economy_model: string;
  fast_model: string;
  reasoning_model: string;
  memory_scopes: string[];
  memory_domain: string;
  memory_count: number;
  credential_configured: boolean;
  profile?: AgentProfile;
};

export type AgentProfile = {
  display_name: string;
  standing_instructions: string;
  response_style: "concise" | "balanced" | "detailed";
  continuity_enabled: boolean;
  decision_routing_enabled: boolean;
};
