export type HubModuleId = "calendar" | "life" | "fitness" | "learning" | "kitchen" | "settings";

export type HubModule = {
  id: HubModuleId;
  label: string;
  path: string;
  distinct?: boolean;
};

export const hubModules: HubModule[] = [
  { id: "calendar", label: "Calendar", path: "/calendar" },
  { id: "life", label: "Life", path: "/life" },
  { id: "fitness", label: "Fitness", path: "/fitness" },
  { id: "learning", label: "Learning", path: "/learning" },
  { id: "kitchen", label: "Kitchen", path: "/kitchen" },
  { id: "settings", label: "Settings", path: "/settings", distinct: true }
];
