import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { GravityWellPreviewPage } from "./GravityWellPreviewPage";
import "../../styles/global.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <GravityWellPreviewPage />
  </StrictMode>
);
