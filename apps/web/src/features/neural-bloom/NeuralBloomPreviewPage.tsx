import { useState } from "react";
import { Canvas } from "@react-three/fiber";
import { Bloom, EffectComposer } from "@react-three/postprocessing";

import { NeuralBloom } from "./NeuralBloom";
import "./neural-bloom.css";

type StageProps = {
  mode: "hero" | "miniature";
  view: "front" | "three-quarter";
  attention: boolean;
};

function BloomStage({ mode, view, attention }: StageProps) {
  const position: [number, number, number] = mode === "miniature"
    ? [0, 0, 11.8]
    : view === "front" ? [0, 0, 4.55] : [2.8, 1.05, 3.8];
  const rotation: [number, number, number] = view === "front" ? [0.02, -0.18, -0.06] : [0.16, 0.48, -0.08];

  return (
    <Canvas
      camera={{ position, fov: view === "front" ? 36 : 38, near: 0.1, far: 30 }}
      dpr={[1, 1]}
      frameloop="demand"
      gl={{ antialias: false, alpha: false, powerPreference: "high-performance" }}
      fallback={<span className="neural-canvas-fallback">WebGL preview unavailable</span>}
    >
      <color attach="background" args={["#050712"]} />
      <ambientLight intensity={0.42} />
      <directionalLight position={[3.4, 4.2, 5]} intensity={2.5} color="#e7dcff" />
      <pointLight position={[-3.2, 0.5, 2.4]} intensity={2.2} color="#7955e8" />
      <pointLight position={[0.8, -2.8, -2.5]} intensity={1.2} color="#38236e" />
      <group rotation={rotation}>
        <NeuralBloom mode={mode} attention={attention} />
      </group>
      <EffectComposer multisampling={0} resolutionScale={0.65}>
        <Bloom
          intensity={1.08}
          luminanceThreshold={0.64}
          luminanceSmoothing={0.2}
          mipmapBlur
          radius={0.76}
        />
      </EffectComposer>
    </Canvas>
  );
}

export function NeuralBloomPreviewPage() {
  const [attention, setAttention] = useState(false);

  return (
    <main className="neural-preview-page">
      <div className="neural-preview-shell">
        <header className="neural-preview-topbar">
          <a className="neural-wordmark" href="/" aria-label="Life OS home">
            <span className="neural-wordmark-icon" aria-hidden="true">
              <span />
            </span>
            <span>LIFE OS</span>
          </a>
          <div className="neural-topbar-context">SPATIAL SYSTEMS <span>/</span> OBJECT STUDY 06</div>
          <span className="neural-review-tag"><i /> LIVE REVIEW</span>
        </header>

        <section className="neural-intro">
          <div>
            <p className="neural-eyebrow">LEARNING DOMAIN <span>·</span> DEPTH 2 OBJECT</p>
            <h1>Neural <em>Bloom</em></h1>
            <p className="neural-intro-copy">
              Knowledge growing through a living cognitive network.
              <span> Procedural geometry, built for hero focus and orbital scale.</span>
            </p>
          </div>
          <div className="neural-intro-mark" aria-hidden="true">
            <span>NB</span>
            <i />
          </div>
        </section>

        <section className="neural-preview-grid" aria-label="Neural Bloom render studies">
          <article className="neural-viewport neural-viewport-hero">
            <div className="neural-viewport-head">
              <div><span className="neural-index">01</span><span>HERO / FRONT</span></div>
              <span className="neural-viewport-note">CENTRIC FORM</span>
            </div>
            <div className="neural-stage neural-stage-hero">
              <div className="neural-stage-coordinate neural-stage-coordinate-left">LEARNING ROOT <b>·</b> 7 MAJOR PATHS</div>
              <BloomStage mode="hero" view="front" attention={attention} />
              <div className="neural-stage-coordinate neural-stage-coordinate-right"><i /> NO BAKED BACKGROUND</div>
            </div>
            <div className="neural-viewport-foot">
              <span>Bright origin</span><i /><span>Branch junctions</span><i /><span>Terminal nodes</span>
            </div>
          </article>

          <aside className="neural-preview-studies">
            <article className="neural-viewport">
              <div className="neural-viewport-head">
                <div><span className="neural-index">02</span><span>THREE-QUARTER</span></div>
                <span className="neural-viewport-note">LAYER DEPTH</span>
              </div>
              <div className="neural-stage neural-stage-detail">
                <BloomStage mode="hero" view="three-quarter" attention={attention} />
              </div>
            </article>

            <article className="neural-viewport neural-viewport-mini">
              <div className="neural-viewport-head">
                <div><span className="neural-index">03</span><span>DEPTH 1 / ORBITAL</span></div>
                <span className="neural-viewport-note">MINIATURE</span>
              </div>
              <div className="neural-stage neural-stage-mini">
                <BloomStage mode="miniature" view="front" attention={attention} />
                <span className="neural-mini-scale">50 PX LEGIBILITY TEST</span>
              </div>
            </article>
          </aside>
        </section>

        <section className="neural-blueprint" aria-label="Layer architecture and material notes">
          <div className="neural-blueprint-heading">
            <div><p className="neural-eyebrow">OBJECT BLUEPRINT</p><h2>Independent layers. One growing signature.</h2></div>
            <span className="neural-procedural-stamp"><i /> PROCEDURAL / R3F</span>
          </div>
          <div className="neural-layer-grid">
            <div><span>01 / ROOT</span><strong>LearningRoot</strong><small>Transform and scale control</small></div>
            <div><span>02 / SHELL</span><strong>OuterShell</strong><small>Violet mineral Fresnel</small></div>
            <div><span>03 / ORIGIN</span><strong>BloomCore</strong><small>Lavender-white focal light</small></div>
            <div><span>04 / NETWORK</span><strong>MajorBranch_A—G</strong><small>Named, luminous curve groups</small></div>
            <div><span>05 / NODES</span><strong>TerminalNodes</strong><small>Independent terminal emitters</small></div>
          </div>
          <div className="neural-blueprint-bottom">
            <div className="neural-material-notes">
              <span className="neural-eyebrow">MATERIAL NOTES</span>
              <p><b>Shell</b> · translucent dark violet <i /> <b>Bloom</b> · lilac emissive tubes <i /> <b>Core</b> · near-white lavender</p>
            </div>
            <div className={`neural-attention-control${attention ? " is-active" : ""}`}>
              <div><span className="neural-eyebrow">STATE STUDY</span><strong>Localized attention signal</strong></div>
              <button type="button" aria-pressed={attention} onClick={() => setAttention((current) => !current)}>
                <i />{attention ? "ATTENTION ON" : "PREVIEW ATTENTION"}
              </button>
            </div>
          </div>
        </section>

        <footer className="neural-preview-footer">
          <span>LEARNING / NEURAL BLOOM</span>
          <span>THREE.JS <i /> REACT THREE FIBER <i /> NO GLB REQUIRED</span>
        </footer>
      </div>
    </main>
  );
}
