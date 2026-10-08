import type { SpatialDomainId } from "./spatialNavigation";

export type SpatialMoon = {
  id: string;
  label: string;
  href: string | null;
  accent: string;
  availability: "ready" | "planned";
};

// Existing workspace sections use real anchors; no canonical data moves with this taxonomy.
// Fitness Nutrition shares Kitchen's existing controls until a separate workspace is designed.
export const spatialMoonCatalog: Readonly<Record<SpatialDomainId, readonly SpatialMoon[]>> = {
  calendar: [
    { id: "calendar", label: "Calendar", href: "/calendar", accent: "#a59bff", availability: "ready" },
    { id: "daily-list", label: "Daily list", href: "/calendar#daily-list", accent: "#a59bff", availability: "ready" },
  ],
  learning: [
    { id: "study-log", label: "Study Log", href: "/learning#study-log", accent: "#d2a7ff", availability: "ready" },
    { id: "study-candidates", label: "Study Candidates", href: "/learning#study-candidates", accent: "#d2a7ff", availability: "ready" },
    { id: "exams", label: "Exams", href: "/learning#exams", accent: "#d2a7ff", availability: "ready" },
  ],
  home: [
    { id: "cleaning", label: "Cleaning", href: null, accent: "#f2c07b", availability: "planned" },
    { id: "kitchen", label: "Kitchen", href: "/kitchen", accent: "#f2c07b", availability: "ready" },
    { id: "shopping", label: "Shopping", href: "/kitchen#shopping", accent: "#f2c07b", availability: "ready" },
  ],
  fitness: [
    { id: "nutrition", label: "Nutrition", href: "/kitchen#nutrition", accent: "#83dfff", availability: "ready" },
    { id: "training", label: "Training", href: "/fitness#training", accent: "#83dfff", availability: "ready" },
  ],
  life: [
    { id: "finance", label: "Finance", href: "/finance", accent: "#94e4c4", availability: "ready" },
    { id: "goals", label: "Goals", href: "/life#goals", accent: "#94e4c4", availability: "ready" },
    { id: "social-life", label: "Social life", href: "/social", accent: "#94e4c4", availability: "ready" },
    { id: "film", label: "Film", href: "/movies", accent: "#94e4c4", availability: "ready" },
    { id: "notebook", label: "Notebook", href: "/notebook", accent: "#94e4c4", availability: "ready" },
  ],
} as const;
