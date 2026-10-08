import { Canvas } from "@react-three/fiber";
import { Bloom, EffectComposer } from "@react-three/postprocessing";
import { useState } from "react";

import { DEFAULT_SUPPLY_CORE_LAYOUT, SupplyCore, type SupplyCorePlateLayout, type SupplyCorePlateState } from "./SupplyCore";
import "./supply-core.css";

const MINIATURE_PLATE_LAYOUT: SupplyCorePlateLayout = {
  ...DEFAULT_SUPPLY_CORE_LAYOUT,
  plateCount: 28,
  jitter: 0.14,
  cornerRadius: 0.23
};

const stateOptions: { id: Exclude<SupplyCorePlateState, "normal">; label: string; shortLabel: string; plates: Record<string, SupplyCorePlateState> }[] = [
  { id: "healthy", label: "Stocked", shortLabel: "Healthy", plates: { "plate-01": "healthy", "plate-02": "healthy", "plate-03": "healthy" } },
  { id: "scheduled", label: "Scheduled", shortLabel: "Planned", plates: { "plate-04": "scheduled", "plate-05": "scheduled", "plate-06": "scheduled" } },
  { id: "warning", label: "Low Supply", shortLabel: "Low", plates: { "plate-01": "warning", "plate-03": "warning", "plate-05": "warning" } },
  { id: "attention", label: "Urgent", shortLabel: "Needs action", plates: { "plate-01": "attention", "plate-02": "attention", "plate-03": "attention" } }
];

function HomeLighting({ miniature = false }: { miniature?: boolean }) {
  return (
    <>
      <ambientLight intensity={miniature ? 0.52 : 0.16} />
      <hemisphereLight args={["#ffe5b8", "#070c12", miniature ? 0.82 : 0.58]} />
      <directionalLight position={[-3.8, 4.2, 4.5]} intensity={miniature ? 2.7 : 1.65} color="#fff0d8" />
      <pointLight position={[-3.2, 2.6, 1.2]} intensity={miniature ? 4.2 : 0.9} distance={8} color="#ffc16d" />
      <pointLight position={[-2.5, -2.2, -1.5]} intensity={miniature ? 1.2 : 0.85} distance={7} color="#557991" />
      <pointLight position={[0.2, 3.4, -2.4]} intensity={miniature ? 1.5 : 1.2} distance={8} color="#dc792f" />
    </>
  );
}

function HomeBloom({ miniature = false }: { miniature?: boolean }) {
  return (
    <EffectComposer multisampling={0} resolutionScale={miniature ? 0.56 : 0.72}>
      <Bloom
      intensity={miniature ? 0.48 : 0.34}
      luminanceThreshold={miniature ? 0.66 : 0.88}
        luminanceSmoothing={0.18}
        mipmapBlur
      radius={0.56}
      />
    </EffectComposer>
  );
}

export function HomeSupplyCorePreview() {
  const [previewState, setPreviewState] = useState<SupplyCorePlateState | "default">("default");
  const selected = stateOptions.find((state) => state.id === previewState);

  return (
    <main className="supply-catalog-page" aria-label="Home Supply Core object preview">
      <div className="supply-catalog-stars" aria-hidden="true" />

      <div className="supply-catalog-shell">
        <header className="supply-catalog-header">
          <a className="supply-catalog-brand" href="/" aria-label="Life OS home">
            <span className="supply-catalog-brand-mark"><i /></span>
            <span>LIFE OS</span>
          </a>
          <span className="supply-catalog-tagline">BUILD A CALMER, BRIGHTER YOU</span>
        </header>

        <div className="supply-catalog-content">
          <section className="supply-catalog-hero" aria-label="Home Supply Core 3D object">
            <div className="supply-catalog-grid" aria-hidden="true" />
            <span className="supply-catalog-cross supply-catalog-cross-a" aria-hidden="true" />
            <span className="supply-catalog-cross supply-catalog-cross-b" aria-hidden="true" />
            <div className="supply-catalog-aura" aria-hidden="true" />
            <Canvas
              camera={{ position: [0, 0.12, 6.2], fov: 33 }}
              dpr={[1, 1.65]}
              frameloop="demand"
              gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }}
              onCreated={({ gl }) => gl.setClearColor("#030812", 0)}
            >
              <HomeLighting />
              <group position={[0, 0.02, 0]} rotation={[0.02, 0, 0.1]}>
                <SupplyCore plateStates={selected?.plates ?? {}} />
              </group>
              <HomeBloom />
            </Canvas>
            <div className="supply-catalog-hero-caption"><span>FIG. 01</span> HOME RESOURCE WORLD <i /> DEPTH 1</div>
            <div className="supply-catalog-depth">{DEFAULT_SUPPLY_CORE_LAYOUT.plateCount} <span>PLATE GROUPS</span></div>
          </section>

          <section className="supply-catalog-details" aria-labelledby="supply-catalog-title">
            <div className="supply-catalog-overline"><span /> DOMAIN <i /> LIFE OS</div>

            <h1 id="supply-catalog-title">HOME <span>—</span> <em>SUPPLY CORE</em></h1>

            <div className="supply-catalog-role">
              <div className="supply-catalog-role-mark" aria-hidden="true"><span /><i /></div>
              <div>
                <h2>Role</h2>
                <p>Domestic resources and logistics, organized as one living system.</p>
                <div className="supply-catalog-domains"><span>Kitchen</span><i /><span>Cleaning</span><i /><span>Supplies</span><i /><span>Responsibilities</span></div>
              </div>
            </div>

            <div className="supply-catalog-motion">
              <div className="supply-catalog-motion-mark" aria-hidden="true">
                <svg viewBox="0 0 76 54" fill="none">
                  <ellipse cx="38" cy="27" rx="32" ry="8.5" transform="rotate(-22 38 27)" />
                  <circle cx="38" cy="27" r="15" />
                  <path d="M8 38c8 1 17-1 24-5m13-12c8-3 16-4 23-2" />
                </svg>
              </div>
              <div>
                <h2>Motion</h2>
                <ul>
                  <li>Slow rotation</li>
                  <li>Panel light shifts</li>
                  <li>Subtle orbit ring</li>
                </ul>
              </div>
            </div>

            <section className="supply-catalog-state-study" aria-labelledby="supply-state-title">
              <div className="supply-catalog-section-head">
                <h2 id="supply-state-title">Plate states</h2>
                <span>LOCAL MATERIAL STUDY</span>
              </div>
              <div className="supply-catalog-miniatures">
                <Canvas
                  camera={{ position: [0, 0, 2.75], fov: 38 }}
                  dpr={[1, 1.4]}
                  frameloop="demand"
                  gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }}
                  onCreated={({ gl }) => gl.setClearColor("#030812", 0)}
                >
                  <HomeLighting miniature />
                  {stateOptions.map((state, index) => (
                    <group key={state.id} position={[(index - 1.5) * 1.02, 0.04, 0]} rotation={[0.02, 0, 0.1]}>
                      <SupplyCore radius={0.39} plateLayout={MINIATURE_PLATE_LAYOUT} plateGap={0.007} plateExtrusion={0.012} emission={0.52} plateStates={state.plates} showOrbit={false} showDetails={false} />
                    </group>
                  ))}
                  <HomeBloom miniature />
                </Canvas>
                <div className="supply-catalog-mini-labels">
                  {stateOptions.map((state) => (
                    <button
                      key={state.id}
                      className={`supply-catalog-state-button state-${state.id}${previewState === state.id ? " is-selected" : ""}`}
                      type="button"
                      aria-pressed={previewState === state.id}
                      onClick={() => setPreviewState((current) => current === state.id ? "default" : state.id)}
                    >
                      <span>{state.label}</span><small>{state.shortLabel}</small>
                    </button>
                  ))}
                </div>
              </div>
              <p className="supply-catalog-state-note">
                {selected ? <><b>{selected.label}</b> is previewed on three addressable plates.</> : <>Default state is warm bronze. Select a plate study to preview localized color.</>}
              </p>
            </section>

            <section className="supply-catalog-color-key" aria-label="Plate state color key">
              <div className="supply-catalog-section-head">
                <h2>State colors</h2>
                <span>ONE PLATE AT A TIME</span>
              </div>
              <div className="supply-catalog-color-list">
                <div className="color-neutral"><i /><span>Neutral</span><small>Default / idle</small></div>
                <div className="color-healthy"><i /><span>Healthy</span><small>On track</small></div>
                <div className="color-scheduled"><i /><span>Scheduled</span><small>Planned</small></div>
                <div className="color-warning"><i /><span>Low supply</span><small>Check soon</small></div>
                <div className="color-attention"><i /><span>Attention</span><small>Needs action</small></div>
              </div>
            </section>
          </section>
        </div>

        <footer className="supply-catalog-footer">
          <span><i /> LIVE PROCEDURAL PREVIEW</span>
          <span>MODULAR PLATES <b>·</b> INDEPENDENT STATE <b>·</b> THREE.JS / R3F</span>
        </footer>
      </div>
    </main>
  );
}
