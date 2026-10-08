import { useEffect, useMemo, useRef } from "react";
import { Canvas, createPortal, useFrame, useThree } from "@react-three/fiber";
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

import { SelfCore } from "./SelfCore";
import "./SelfCorePreview.css";

function makeDistantStars(count: number, seed: number) {
  let state = seed >>> 0;
  const random = () => {
    state = (state * 1664525 + 1013904223) >>> 0;
    return state / 4294967296;
  };

  const positions = new Float32Array(count * 3);
  for (let index = 0; index < count; index += 1) {
    const z = random() * 2 - 1;
    const angle = random() * Math.PI * 2;
    const planar = Math.sqrt(1 - z * z);
    const radius = 10 + random() * 13;
    positions[index * 3] = Math.cos(angle) * planar * radius;
    positions[index * 3 + 1] = Math.sin(angle) * planar * radius;
    positions[index * 3 + 2] = z * radius;
  }

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  return geometry;
}

function Starfield({ count = 720 }: { count?: number }) {
  const geometry = useMemo(() => makeDistantStars(count, 227), [count]);

  return (
    <points name="DistantStars" geometry={geometry} frustumCulled={false}>
      <pointsMaterial
        color="#9fcdf5"
        size={1.35}
        sizeAttenuation={false}
        transparent
        opacity={0.38}
        depthWrite={false}
        toneMapped={false}
      />
    </points>
  );
}

function PreviewOrbitControls() {
  const controls = useRef<OrbitControls | null>(null);
  const { camera, gl } = useThree();

  useEffect(() => {
    const instance = new OrbitControls(camera, gl.domElement);
    instance.enableDamping = true;
    instance.dampingFactor = 0.075;
    instance.enablePan = false;
    instance.rotateSpeed = 0.48;
    instance.minDistance = 2.8;
    instance.maxDistance = 8;
    controls.current = instance;

    return () => {
      instance.dispose();
      controls.current = null;
    };
  }, [camera, gl]);

  useFrame(() => controls.current?.update());
  return null;
}

function MainScene() {
  return (
    <>
      <Starfield />
      <SelfCore scale={1.3} />
      <MiniaturePass />
      <PreviewOrbitControls />
    </>
  );
}

function MiniaturePass() {
  const { camera, gl, scene, size } = useThree();
  const miniScene = useMemo(() => new THREE.Scene(), []);
  const miniCamera = useMemo(() => new THREE.PerspectiveCamera(43, 1, 0.1, 24), []);

  useFrame(() => {
    const mobile = size.width <= 700;
    const cardWidth = mobile ? 150 : 216;
    const cardHeight = mobile ? 128 : 178;
    const right = mobile ? 20 : THREE.MathUtils.clamp(size.width * 0.046, 25, 70);
    const bottom = mobile ? 68 : THREE.MathUtils.clamp(size.height * 0.12, 72, 112);
    const x = Math.max(0, size.width - right - cardWidth);
    const y = Math.max(0, bottom);

    gl.setScissorTest(false);
    gl.setViewport(0, 0, size.width, size.height);
    gl.render(scene, camera);
    gl.clearDepth();

    miniCamera.aspect = cardWidth / cardHeight;
    miniCamera.position.set(0, 0, 3.15);
    miniCamera.lookAt(0, 0, 0);
    miniCamera.updateProjectionMatrix();
    gl.setScissorTest(true);
    gl.setScissor(x, y, cardWidth, cardHeight);
    gl.setViewport(x, y, cardWidth, cardHeight);
    gl.render(miniScene, miniCamera);
    gl.setScissorTest(false);
    gl.setViewport(0, 0, size.width, size.height);
  }, 1);

  return createPortal(
    <>
      <Starfield count={72} />
      <SelfCore scale={0.95} />
    </>,
    miniScene
  );
}

export function SelfCorePreview() {
  return (
    <main className="self-core-preview">
      <div className="self-core-preview__backdrop" aria-hidden="true" />
      <Canvas
        className="self-core-preview__main-canvas"
        camera={{ position: [0, 0, 6.1], fov: 42, near: 0.1, far: 80 }}
        dpr={[1, 1.8]}
        gl={{ alpha: true, antialias: true, powerPreference: "high-performance" }}
        aria-label="Interactive 3D preview of Self Core"
        fallback={<div className="self-core-preview__fallback">3D preview unavailable</div>}
      >
        <MainScene />
      </Canvas>

      <header className="self-core-preview__header">
        <a className="self-core-preview__brand" href="/" aria-label="Life OS home">
          <span className="self-core-preview__brand-mark" aria-hidden="true" />
          <span>LIFE OS <span className="self-core-preview__brand-divider">/</span> SPATIAL SYSTEM</span>
        </a>
        <span className="self-core-preview__depth">DEPTH <strong>00</strong></span>
      </header>

      <section className="self-core-preview__intro" aria-label="Object identity">
        <p className="self-core-preview__eyebrow">CENTRAL INTELLIGENCE</p>
        <h1>Self Core</h1>
        <p className="self-core-preview__caption">A compact source of light, held in deep space.</p>
      </section>

      <div className="self-core-preview__interaction" aria-label="Preview controls">
        <span className="self-core-preview__interaction-icon" aria-hidden="true">↗</span>
        <span>DRAG TO ORBIT <i /> SCROLL TO APPROACH</span>
      </div>

      <aside className="self-core-preview__miniature" aria-label="Self Core at miniature navigation scale">
        <div className="self-core-preview__miniature-heading">
          <span>MINIATURE</span>
          <span>NAVIGATION SCALE</span>
        </div>
      </aside>

      <footer className="self-core-preview__footer">
        <span>WHITE-HOT CORE <i /> BLUE CORONA <i /> THREE INDEPENDENT ORBITS</span>
        <span>PROCEDURAL STUDY <b>01</b></span>
      </footer>
    </main>
  );
}
