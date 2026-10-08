import { Canvas } from "@react-three/fiber";
import { useState } from "react";

import { OrbitBarbell, type OrbitBarbellView } from "./OrbitBarbell";
import "./orbit-barbell-preview.css";

const views: { id: OrbitBarbellView; label: string }[] = [
  { id: "front", label: "Front" },
  { id: "three-quarter", label: "3/4 view" },
  { id: "side", label: "Side" },
];

export function FitnessOrbitPreviewPage() {
  const [view, setView] = useState<OrbitBarbellView>("three-quarter");
  const [attention, setAttention] = useState(false);

  return (
    <div className="orbit-preview-page">
      <header className="orbit-preview-header">
        <a className="orbit-preview-brand" href="/" aria-label="Life OS home">
          <span className="orbit-preview-brand-mark"><i /></span>
          <span>LIFE OS</span>
        </a>
        <span className="orbit-preview-index">DOMAIN OBJECT <b>01 / 05</b></span>
        <span className="orbit-preview-header-right">VISUAL STUDY <i /> FITNESS</span>
      </header>

      <main className="orbit-preview-main">
        <section className="orbit-preview-title" aria-label="Object introduction">
          <p className="orbit-preview-kicker"><span /> FITNESS DOMAIN</p>
          <h1>Orbit<br /><em>Barbell</em></h1>
          <p className="orbit-preview-description">Strength, balance, and structure held in orbit around a dark athletic core.</p>
          <div className="orbit-preview-properties">
            <span>01 <b>PLANET CORE</b></span>
            <span>02 <b>CYAN ORBIT</b></span>
            <span>03 <b>BALANCED MASSES</b></span>
          </div>
        </section>

        <section className="orbit-preview-stage" aria-label="Interactive Orbit Barbell 3D preview">
          <div className="orbit-preview-stage-grid" />
          <div className="orbit-preview-stage-crosshair orbit-preview-stage-crosshair--top" />
          <div className="orbit-preview-stage-crosshair orbit-preview-stage-crosshair--bottom" />
          <Canvas
            orthographic
            camera={{ position: [0, 0, 50], zoom: 110 }}
            dpr={[1, 1.5]}
            frameloop="demand"
            gl={{ alpha: true, antialias: true, powerPreference: "high-performance" }}
            onCreated={({ gl }) => gl.setClearColor("#03060b", 0)}
          >
            <ambientLight intensity={0.48} />
            <hemisphereLight args={["#c7efff", "#030914", 0.88]} />
            <directionalLight position={[-3.4, 4, 5]} intensity={2.7} color="#e2f7ff" />
            <pointLight position={[-2, 1.1, 3.1]} intensity={25} distance={9} color="#48c6f2" />
            <pointLight position={[2.8, -0.6, 3.5]} intensity={17} distance={8} color="#5fd6ff" />
            <pointLight position={[0, 0.4, 4.6]} intensity={12} distance={10} color="#68ccf2" />
            <pointLight position={[0, -2, -4]} intensity={4} distance={9} color="#16799c" />
            <OrbitBarbell view={view} attention={attention} />
          </Canvas>
          <div className="orbit-preview-stage-caption"><span>FIG. 01</span> DOMAIN PLANET <i /> DEPTH 1</div>
          <div className="orbit-preview-stage-coordinate">01 / <span>03</span></div>
        </section>

        <aside className="orbit-preview-side-panel" aria-label="Preview settings">
          <div className="orbit-preview-side-panel-heading"><span>01</span> OBJECT STATE</div>
          <button
            className={`orbit-preview-attention-toggle${attention ? " is-active" : ""}`}
            type="button"
            aria-pressed={attention}
            onClick={() => setAttention((current) => !current)}
          >
            <span className="orbit-preview-state-light" />
            <span>{attention ? "Attention" : "Active"}<small>{attention ? "Localized signal" : "Cyan identity"}</small></span>
            <span className="orbit-preview-toggle-track"><i /></span>
          </button>
          <div className="orbit-preview-side-rule" />
          <p className="orbit-preview-side-label">MATERIAL LANGUAGE</p>
          <div className="orbit-preview-swatches">
            <span><i className="swatch-core" />ATHLETIC BLUE</span>
            <span><i className="swatch-cyan" />ELECTRIC CYAN</span>
            <span><i className="swatch-ice" />ICE BLUE</span>
          </div>
          <div className="orbit-preview-side-rule" />
          <p className="orbit-preview-side-label">GEOMETRY</p>
          <p className="orbit-preview-side-copy">Procedural · real-time<br />Independently addressable groups</p>
          <div className="orbit-preview-miniature">
            <div className="orbit-preview-miniature-label"><span>DEPTH 1 SCALE</span><b>MINIATURE</b></div>
            <div className="orbit-preview-miniature-canvas">
              <Canvas
                orthographic
                camera={{ position: [0, 0, 50], zoom: 38 }}
                dpr={[1, 1.35]}
                frameloop="demand"
                gl={{ alpha: true, antialias: true }}
                onCreated={({ gl }) => gl.setClearColor("#03060b", 0)}
              >
                <ambientLight intensity={0.5} />
                <hemisphereLight args={["#c6edff", "#030812", 0.86]} />
                <directionalLight position={[-2, 3, 4]} intensity={2.4} color="#e5f8ff" />
                <pointLight position={[-1.5, 0.6, 2]} intensity={16} distance={7} color="#3cbce9" />
                <pointLight position={[0, 0.3, 3.2]} intensity={11} distance={8} color="#54c5ed" />
                <OrbitBarbell variant="miniature" view="three-quarter" />
              </Canvas>
            </div>
            <span className="orbit-preview-miniature-note">SILHOUETTE REMAINS LEGIBLE</span>
          </div>
        </aside>
      </main>

      <footer className="orbit-preview-footer">
        <div className="orbit-preview-footer-legend"><span className="orbit-preview-live-dot" /> LIVE OBJECT PREVIEW <i /> WEBGL / PROCEDURAL</div>
        <div className="orbit-preview-view-controls" aria-label="Object view">
          <span>VIEW</span>
          {views.map((item) => (
            <button
              aria-pressed={view === item.id}
              className={view === item.id ? "is-selected" : ""}
              key={item.id}
              onClick={() => setView(item.id)}
              type="button"
            >
              {item.label}
            </button>
          ))}
        </div>
        <div className="orbit-preview-footer-note">STRENGTH FUELS A BETTER YOU</div>
      </footer>
    </div>
  );
}
