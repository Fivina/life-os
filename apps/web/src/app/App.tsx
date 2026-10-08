import { lazy, Suspense } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { AssistantPage } from "../features/assistant/AssistantPage";
import { CalendarPage } from "../features/calendar/CalendarPage";
import { LoginPage } from "../features/auth/LoginPage";
import { FitnessPage } from "../features/fitness/FitnessPage";
import { FitnessOrbitPreviewPage } from "../features/fitness/FitnessOrbitPreviewPage";
import { FinancePage } from "../features/finance/FinancePage";
import { SpatialHomeRedirect } from "../features/hub/SpatialHomeRedirect";
import { KitchenPage } from "../features/kitchen/KitchenPage";
import { HomeSupplyCorePreview } from "../features/home/HomeSupplyCorePreview";
import { LearningPage } from "../features/learning/LearningPage";
import { LifePage } from "../features/life/LifePage";
import { PersonalModelPage } from "../features/personal-model/PersonalModelPage";
import { SettingsPage } from "../features/settings/SettingsPage";
import { NotebookPage } from "../features/notebook/NotebookPage";
import { MoviesPage } from "../features/movies/MoviesPage";
import { SocialPage } from "../features/social/SocialPage";
import { ProtectedRoute } from "../features/auth/ProtectedRoute";
import { AppShell } from "../layouts/AppShell";
import { AppProviders } from "./providers";

const NeuralBloomPreviewPage = import.meta.env.DEV
  ? lazy(async () => {
      const module = await import("../features/neural-bloom/NeuralBloomPreviewPage");
      return { default: module.NeuralBloomPreviewPage };
    })
  : null;

const LifeCoreEarthPreviewPage = import.meta.env.DEV
  ? lazy(async () => {
      const module = await import("../features/life/CoreEarthPreview");
      return { default: module.CoreEarthPreviewPage };
    })
  : null;

const GravityWellPreviewPage = lazy(async () => {
  const module = await import("../features/settings-gravity-well/GravityWellPreviewPage");
  return { default: module.GravityWellPreviewPage };
});

const SelfCorePreviewPage = import.meta.env.DEV
  ? lazy(async () => {
      const module = await import("../features/hub/three/SelfCorePreview");
      return { default: module.SelfCorePreview };
    })
  : null;

const SystemArtPreviewPage = lazy(() => import("../features/hub/SystemArtPreviewPage"));
const PhengosHome = lazy(() => import("../features/phengos/PhengosHome"));

export function App() {
  return (
    <AppProviders>
      <BrowserRouter>
        <Routes>
          {import.meta.env.DEV && <Route path="/_dev/system-art" element={
            <Suspense fallback={<main>Loading system art...</main>}><SystemArtPreviewPage /></Suspense>
          } />}
          {SelfCorePreviewPage && (
            <Route
              path="/_dev/self-core"
              element={
                <Suspense fallback={<main className="self-core-preview-loading" />}>
                  <SelfCorePreviewPage />
                </Suspense>
              }
            />
          )}
          {NeuralBloomPreviewPage && (
            <Route
              path="/_dev/neural-bloom"
              element={
                <Suspense fallback={<main>Loading Neural Bloom preview…</main>}>
                  <NeuralBloomPreviewPage />
                </Suspense>
              }
            />
          )}
          {import.meta.env.DEV && (
            <Route
              path="/_dev/dark-hole"
              element={
                <Suspense fallback={<main>Loading Gravity Well preview…</main>}>
                  <GravityWellPreviewPage />
                </Suspense>
              }
            />
          )}
          {LifeCoreEarthPreviewPage && (
            <Route
              path="/_dev/life-core-earth"
              element={
                <Suspense fallback={<main>Loading Core Earth preview…</main>}>
                  <LifeCoreEarthPreviewPage />
                </Suspense>
              }
            />
          )}
          {import.meta.env.DEV && <Route path="/_dev/home-supply-core" element={<HomeSupplyCorePreview />} />}
          <Route path="/login" element={<LoginPage />} />
          <Route path="/_preview/fitness-orbit" element={<FitnessOrbitPreviewPage />} />
          <Route element={<ProtectedRoute />}>
            <Route path="/" element={<Suspense fallback={<main>Life OS</main>}><PhengosHome /></Suspense>} />
            <Route path="/space" element={<SpatialHomeRedirect />} />
            <Route element={<AppShell />}>
              <Route path="/self" element={<Navigate to="/self/assistant" replace />} />
              <Route path="/self/assistant" element={<AssistantPage />} />
              <Route path="/calendar" element={<CalendarPage />} />
              <Route path="/life" element={<LifePage />} />
              <Route path="/fitness" element={<FitnessPage />} />
              <Route path="/learning" element={<LearningPage />} />
              <Route path="/kitchen" element={<KitchenPage />} />
              <Route path="/finance" element={<FinancePage />} />
              <Route path="/settings" element={<SettingsPage />} />
              <Route path="/notebook" element={<NotebookPage />} />
              <Route path="/movies" element={<MoviesPage />} />
              <Route path="/social" element={<SocialPage />} />
              <Route path="/settings/personal-model" element={<PersonalModelPage />} />
              <Route path="/assistant" element={<Navigate to="/self/assistant" replace />} />
              <Route path="/personal-model" element={<Navigate to="/settings/personal-model" replace />} />
            </Route>
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AppProviders>
  );
}
