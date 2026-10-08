import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { ChronoRingPreview } from "./ChronoRingPreview";

const mount = document.getElementById("chrono-ring-root");

if (!mount) {
  throw new Error("Chrono Ring preview root was not found.");
}

createRoot(mount).render(
  <StrictMode>
    <ChronoRingPreview />
  </StrictMode>
);
