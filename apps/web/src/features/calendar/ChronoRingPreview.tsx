import { useEffect } from "react";
import { Canvas, useThree } from "@react-three/fiber";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import * as THREE from "three";

import { ChronoRing } from "./ChronoRing";
import "./chrono-ring-preview.css";

function PreviewOrbitControls() {
  const { camera, gl, invalidate } = useThree();

  useEffect(() => {
    const controls = new OrbitControls(camera, gl.domElement);
    controls.enableDamping = false;
    controls.enablePan = false;
    controls.minDistance = 4.2;
    controls.maxDistance = 14;
    controls.minPolarAngle = 0.2;
    controls.maxPolarAngle = Math.PI - 0.2;

    const renderOnChange = () => invalidate();
    controls.addEventListener("change", renderOnChange);
    controls.update();
    invalidate();

    return () => {
      controls.removeEventListener("change", renderOnChange);
      controls.dispose();
    };
  }, [camera, gl, invalidate]);

  return null;
}

function Lighting() {
  return (
    <>
      <ambientLight color="#7783be" intensity={0.09} />
      <hemisphereLight args={["#dce5ff", "#080b1c", 0.24]} />
      <directionalLight
        color="#a8beff"
        intensity={4.5}
        position={[-5.5, 3.5, 3.2]}
        castShadow
        shadow-mapSize-width={1024}
        shadow-mapSize-height={1024}
      />
      <directionalLight color="#586eff" intensity={0.35} position={[5, 1, -4]} />
      <directionalLight color="#3c55d6" intensity={0.35} position={[4, -4, 5]} />
      <directionalLight color="#6684ff" intensity={2.8} position={[-4, 2, -5]} />
    </>
  );
}

function ObjectStage({ variant }: { variant: "hero" | "miniature" }) {
  const cameraPosition: [number, number, number] =
    variant === "hero" ? [3.9, 2.93, 5.85] : [5.4, 4.05, 8.1];

  return (
    <Canvas
      shadows
      dpr={[1, 1.75]}
      camera={{ position: cameraPosition, fov: 23.5, near: 0.1, far: 100 }}
      gl={{
        antialias: true,
        toneMapping: THREE.ACESFilmicToneMapping,
        outputColorSpace: THREE.SRGBColorSpace
      }}
      frameloop="demand"
    >
      <color attach="background" args={["#050814"]} />
      <Lighting />
      <ChronoRing variant={variant} />
      <PreviewOrbitControls />
    </Canvas>
  );
}

export function ChronoRingPreview() {
  return (
    <main className="chrono-preview">
      <header className="chrono-preview__header">
        <div>
          <p className="chrono-preview__eyebrow">LIFE OS · DOMAIN OBJECT</p>
          <h1>Chrono Ring</h1>
          <p className="chrono-preview__subtitle">Calendar · time, sequence, commitments</p>
        </div>
        <div className="chrono-preview__spec">
          <span className="chrono-preview__status-dot" />
          <span>Drag to rotate</span>
          <span className="chrono-preview__spec-divider" />
          <span>Scroll or pinch to zoom</span>
        </div>
      </header>

      <section className="chrono-preview__stages" aria-label="Chrono Ring visual states">
        <article className="chrono-preview__card chrono-preview__card--hero">
          <div className="chrono-preview__card-heading">
            <div>
              <p className="chrono-preview__eyebrow">DEPTH 2 · FOCUSED</p>
              <h2>Hero</h2>
            </div>
            <span>Centric object</span>
          </div>
          <div className="chrono-preview__canvas chrono-preview__canvas--hero">
            <ObjectStage variant="hero" />
          </div>
        </article>

        <article className="chrono-preview__card chrono-preview__card--mini">
          <div className="chrono-preview__card-heading">
            <div>
              <p className="chrono-preview__eyebrow">DEPTH 1 · NAVIGATION</p>
              <h2>Miniature</h2>
            </div>
            <span>Domain planet</span>
          </div>
          <div className="chrono-preview__canvas chrono-preview__canvas--mini">
            <ObjectStage variant="miniature" />
          </div>
          <p className="chrono-preview__caption">Ring segments and the NOW marker remain distinct at reduced scale. Drag to inspect.</p>
        </article>
      </section>

      <footer className="chrono-preview__footer">
        <span>INDIGO CORE</span>
        <span className="chrono-preview__footer-line" />
        <span>VIOLET SEGMENTS</span>
        <span className="chrono-preview__footer-line" />
        <span>MOONLIGHT NOW</span>
      </footer>
    </main>
  );
}
