import { BookOpen, CalendarDays, CircleDot, Dumbbell, Film, House, Leaf, ListChecks, NotebookPen, Settings, ShoppingCart, Target, Users, Utensils, WalletCards } from "lucide-react";

// These are existing workflows, not a new canonical domain hierarchy.
export const phengosFeatures = [
  { label: "Chat", detail: "Plan, review, and ask PHENGOS", href: "/chat", icon: CircleDot, group: "Self", color: "#ffffff" },
  { label: "Calendar", detail: "Shape plans and commitments", href: "/calendar", icon: CalendarDays, group: "Calendar", color: "#f59e0b" },
  { label: "Daily list", detail: "See and complete today's actions", href: "/calendar#daily-list", icon: ListChecks, group: "Calendar", color: "#f59e0b" },
  { label: "Kitchen", detail: "Plan meals and manage food", href: "/kitchen", icon: Utensils, group: "Home", color: "#3b82f6" },
  { label: "Shopping", detail: "Review needs and shopping actions", href: "/kitchen#shopping", icon: ShoppingCart, group: "Home", color: "#3b82f6" },
  { label: "Household", detail: "Track recurring home tasks", href: "/life#household", icon: House, group: "Home", color: "#3b82f6" },
  { label: "Fitness", detail: "Track fitness and progression", href: "/fitness", icon: Dumbbell, group: "Fitness", color: "#06b6d4" },
  { label: "Training", detail: "Run workouts and record sets", href: "/fitness#training", icon: Dumbbell, group: "Fitness", color: "#06b6d4" },
  { label: "Nutrition", detail: "Set targets and log meals", href: "/kitchen#nutrition", icon: Leaf, group: "Home", color: "#06b6d4" },
  { label: "Learning", detail: "Follow courses and progress", href: "/learning", icon: BookOpen, group: "Learning", color: "#a855f7" },
  { label: "Study log", detail: "Record study and learning progress", href: "/learning#study-log", icon: BookOpen, group: "Learning", color: "#a855f7" },
  { label: "Study candidates", detail: "Review possible learning topics", href: "/learning#study-candidates", icon: ListChecks, group: "Learning", color: "#a855f7" },
  { label: "Exams", detail: "Keep exam dates in view", href: "/learning#exams", icon: CalendarDays, group: "Learning", color: "#a855f7" },
  { label: "Life", detail: "See your life overview", href: "/life", icon: CircleDot, group: "Life", color: "#22c55e" },
  { label: "Goals", detail: "Set goals and view trajectory", href: "/life#goals", icon: Target, group: "Life", color: "#22c55e" },
  { label: "Finance", detail: "Review budgets and transactions", href: "/finance", icon: WalletCards, group: "Life", color: "#22c55e" },
  { label: "Social", detail: "Manage activities and opportunities", href: "/social", icon: Users, group: "Life", color: "#22c55e" },
  { label: "Movies", detail: "Manage your movie library", href: "/movies", icon: Film, group: "Life", color: "#22c55e" },
  { label: "Notebook", detail: "Capture, review, and promote ideas", href: "/notebook", icon: NotebookPen, group: "Life", color: "#22c55e" },
  { label: "Settings", detail: "Configure providers and preferences", href: "/settings", icon: Settings, group: "System", color: "#8ea9c7" },
  { label: "Personal model", detail: "Review patterns and model memory", href: "/settings/personal-model", icon: CircleDot, group: "System", color: "#8ea9c7" },
] as const;
