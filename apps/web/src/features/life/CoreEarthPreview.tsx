import { useState } from "react";
import { Canvas } from "@react-three/fiber";

import { CORE_EARTH_PALETTE, CoreEarth, type CoreEarthView } from "./CoreEarth";
import "./core-earth-preview.css";

const materialRows = [
  ["Ocean", CORE_EARTH_PALETTE.ocean],
  ["Living regions", CORE_EARTH_PALETTE.livingLand],
  ["Atmosphere", CORE_EARTH_PALETTE.atmosphere],
  ["Clouds", CORE_EARTH_PALETTE.clouds],
  ["Life lights", CORE_EARTH_PALETTE.lifeLights]
] as const;

const viewChoices: { id: CoreEarthView; label: string }[] = [
  { id: "front", label: "Front" },
  { id: "three-quarter", label: "3/4 view" },
  { id: "side", label: "Side" }
];

export function CoreEarthPreviewPage() {
  const [attentionSignal, setAttentionSignal] = useState(false);
  const [view, setView] = useState<CoreEarthView>("three-quarter");

  return (
    <div className="core-earth-preview">
      <header className="core-earth-preview__header">
        <a className="core-earth-preview__brand" href="/" aria-label="Life OS home">
          <span className="core-earth-preview__brand-mark"><i /></span>
          <span>LIFE OS</span>
        </a>
        <span className="core-earth-preview__index">DOMAIN OBJECT <b>05 / 05</b></span>
        <span className="core-earth-preview__header-right">VISUAL STUDY <i /> LIFE</span>
      </header>

      <main className="core-earth-preview__main">
        <section className="core-earth-preview__title" aria-label="Object introduction">
          <p className="core-earth-preview__kicker"><span /> LIFE DOMAIN</p>
          <h1>Core<br /><em>Earth</em></h1>
          <p className="core-earth-preview__description">A living world for goals, projects, social life, and commitments.</p>
          <div className="core-earth-preview__properties">
            <span>01 <b>PLANET SURFACE</b></span>
            <span>02 <b>CYAN ATMOSPHERE</b></span>
            <span>03 <b>SPARSE LIFE LIGHTS</b></span>
          </div>
        </section>

        <section className="core-earth-preview__stage" aria-label="Interactive Core Earth 3D preview">
          <div className="core-earth-preview__stage-grid" />
          <Canvas
            camera={{ position: [2.85, 1.05, 3.75], fov: 38 }}
            dpr={[1, 1.5]}
            frameloop="demand"
            gl={{ alpha: true, antialias: true, powerPreference: "low-power" }}
            fallback={<span className="core-earth-preview__fallback">3D preview unavailable</span>}
            onCreated={({ gl }) => gl.setClearColor("#020813", 0)}
          >
            <CoreEarth attentionSignal={attentionSignal} view={view} />
          </Canvas>
          <div className="core-earth-preview__stage-caption"><span>FIG. 01</span> DOMAIN PLANET <i /> DEPTH 1</div>
          <div className="core-earth-preview__stage-coordinate">01 / <span>03</span></div>
        </section>

        <aside className="core-earth-preview__side-panel" aria-label="Preview settings">
          <div className="core-earth-preview__side-panel-heading"><span>01</span> OBJECT STATE</div>
          <button
            className={`core-earth-preview__attention-toggle${attentionSignal ? " is-active" : ""}`}
            type="button"
            aria-pressed={attentionSignal}
            onClick={() => setAttentionSignal((current) => !current)}
          >
            <span className="core-earth-preview__state-light" />
            <span>{attentionSignal ? "Attention" : "Active"}<small>{attentionSignal ? "Localized orbit signal" : "Blue-green identity"}</small></span>
            <span className="core-earth-preview__toggle-track"><i /></span>
          </button>
          <p className="core-earth-preview__attention-note">Attention adds one red orbit point; the planet keeps its native colors.</p>
          <div className="core-earth-preview__side-rule" />
          <p className="core-earth-preview__side-label">MATERIAL LANGUAGE</p>
          <div className="core-earth-preview__swatches">
            {materialRows.map(([label, color]) => (
              <span key={label}><i style={{ backgroundColor: color }} />{label}</span>
            ))}
          </div>
          <div className="core-earth-preview__side-rule" />
          <p className="core-earth-preview__side-label">GEOMETRY</p>
          <p className="core-earth-preview__side-copy">Procedural surface and cloud field<br />Independent atmosphere and lights</p>
          <div className="core-earth-preview__miniature">
            <div className="core-earth-preview__miniature-label"><span>DEPTH 1 SCALE</span><b>MINIATURE</b></div>
            <div className="core-earth-preview__miniature-canvas" role="img" aria-label="Miniature Core Earth model">
              <Canvas
                camera={{ position: [2.2, 0.78, 2.9], fov: 38 }}
                dpr={[1, 1.35]}
                frameloop="demand"
                gl={{ alpha: true, antialias: true, powerPreference: "low-power" }}
                onCreated={({ gl }) => gl.setClearColor("#030914", 0)}
              >
                <CoreEarth radius={0.64} presentation="miniature" lifeLightDensity={0.42} />
              </Canvas>
            </div>
            <span className="core-earth-preview__miniature-note">BLUE-GREEN IDENTITY HOLDS AT SMALL SCALE</span>
          </div>
        </aside>
      </main>

      <section className="core-earth-preview__layers" aria-label="Model layer hierarchy">
        <div className="core-earth-preview__layers-heading"><span>SEPARATE MODEL LAYERS</span>Surface · atmosphere · cloud · life-light · orbit</div>
        <div className="core-earth-preview__layer-list">
          {["LifeRoot", "PlanetSurface", "LivingRegionMaterial", "Atmosphere", "CloudLayer", "LifeLights", "OrbitElements"].map((layer, index) => (
            <span key={layer}><i>{String(index + 1).padStart(2, "0")}</i>{layer}</span>
          ))}
        </div>
      </section>
      <footer className="core-earth-preview__footer">
        <div className="core-earth-preview__footer-legend"><span /> LIVE OBJECT PREVIEW <i /> WEBGL / PROCEDURAL</div>
        <div className="core-earth-preview__view-controls" aria-label="Object view">
          <span>VIEW</span>
          {viewChoices.map((item) => (
            <button
              key={item.id}
              type="button"
              aria-pressed={view === item.id}
              className={view === item.id ? "is-selected" : ""}
              onClick={() => setView(item.id)}
            >
              {item.label}
            </button>
          ))}
        </div>
        <div className="core-earth-preview__footer-note">THE USER'S LIVING WORLD</div>
      </footer>
    </div>
  );
}
