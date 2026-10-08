import { Canvas } from "@react-three/fiber";

import { SettingsGravityWell, type SettingsGravityWellProps } from "./SettingsGravityWell";
import "./gravity-well-preview.css";

type GravityWellState = {
  id: string;
  label: string;
  description: string;
  intensity: number;
  distortion: number;
  density: number;
  halo: number;
  open?: boolean;
};

const states: GravityWellState[] = [
  { id: "dormant", label: "Dormant", description: "Low activity, minimal flow", intensity: 0.55, distortion: 0.18, density: 7, halo: 0.12 },
  { id: "hovered", label: "Hovered", description: "Subtle brightening, responsive flow", intensity: 0.78, distortion: 0.34, density: 9, halo: 0.2 },
  { id: "focused", label: "Focused", description: "Stronger lensing, flow converges", intensity: 1, distortion: 0.5, density: 11, halo: 0.3 },
  { id: "open", label: "Open", description: "Inner layers revealed", intensity: 0.92, distortion: 0.55, density: 12, halo: 0.28, open: true }
];

function GravityWellCanvas() {
  return (
    <Canvas
      camera={{ position: [0, 0, 7.5], fov: 34 }}
      dpr={[1, 1.5]}
      frameloop="demand"
      gl={{ alpha: true, antialias: true, powerPreference: "low-power" }}
      fallback={<span className="gravity-canvas-fallback">3D preview unavailable</span>}
    >
      <SettingsGravityWell voidRadius={0.9} lensingRadius={0.99} flowDensity={10} flowRadius={3.8} haloIntensity={0.66} />
    </Canvas>
  );
}

function GravityWellStateStudy({ state }: { state: GravityWellState }) {
  const tracks = [
    "M 4 25 C 93 16 108 33 125 56 C 146 84 168 91 225 80 C 265 72 291 63 316 50",
    "M 7 37 C 82 28 108 42 125 60 C 146 82 173 94 224 85 C 266 78 292 65 319 48",
    "M 4 53 C 76 42 105 51 123 65 C 144 82 173 94 218 92 C 263 88 294 69 320 44",
    "M 12 68 C 78 56 103 60 120 71 C 140 84 166 96 208 97 C 256 97 293 73 321 38",
    "M 19 84 C 82 67 105 69 122 78 C 143 90 167 100 200 103 C 244 106 284 79 319 30",
    "M 30 99 C 87 77 109 77 127 84 C 147 93 169 101 197 108 C 231 117 274 89 311 23",
    "M 10 15 C 95 13 117 33 132 54 C 153 81 183 88 229 76 C 266 66 295 53 323 34",
    "M 3 45 C 79 37 108 47 124 62 C 148 84 175 91 220 88 C 261 86 293 70 319 42",
    "M 17 92 C 79 72 102 72 122 81 C 146 92 170 104 205 107 C 249 110 283 86 315 26",
    "M 1 22 C 76 19 104 31 122 49 C 143 69 159 78 194 74 C 246 69 282 52 322 39",
    "M 5 30 C 71 25 101 37 119 56 C 138 76 158 86 193 83 C 238 80 281 60 322 45",
    "M 8 40 C 72 34 99 42 117 61 C 137 83 160 93 197 91 C 240 89 284 68 320 51",
    "M 6 60 C 69 47 95 51 114 67 C 137 87 158 99 193 102 C 237 106 279 82 319 59",
    "M 14 77 C 77 59 99 60 116 74 C 137 91 158 103 191 109 C 232 116 271 95 316 67",
    "M 24 105 C 81 81 101 76 120 84 C 141 94 162 108 190 115 C 222 124 260 108 308 75",
    "M 2 49 C 65 41 95 44 115 60 C 137 79 154 88 183 88 C 227 88 279 71 321 56",
    "M 11 11 C 89 10 113 28 130 48 C 153 74 178 79 220 69 C 267 58 297 42 324 28"
  ];
  const opacity = state.id === "dormant" ? 0.36 : state.id === "hovered" ? 0.5 : 0.67;
  const ringOpacity = state.id === "dormant" ? 0.52 : state.id === "hovered" ? 0.7 : 0.94;

  return (
    <svg className={`gravity-state-study gravity-state-study--${state.id}`} viewBox="0 0 324 142" role="img" aria-label={`${state.label} gravity well state`}>
      <defs>
        <radialGradient id={`well-fill-${state.id}`}>
          <stop offset="76%" stopColor="#000105" />
          <stop offset="95%" stopColor="#000105" />
          <stop offset="100%" stopColor="#071421" />
        </radialGradient>
        <linearGradient id={`well-ring-${state.id}`} x1="0" y1="1" x2="0.8" y2="0">
          <stop offset="0%" stopColor="#2f9bc9" stopOpacity="0.2" />
          <stop offset="44%" stopColor="#85dbff" stopOpacity="0.8" />
          <stop offset="74%" stopColor="#e5f8ff" stopOpacity="1" />
          <stop offset="100%" stopColor="#67b9e1" stopOpacity="0.42" />
        </linearGradient>
        <filter id={`well-glow-${state.id}`} x="-80%" y="-80%" width="260%" height="260%">
          <feGaussianBlur stdDeviation="2.5" />
        </filter>
      </defs>
      <g fill="none" stroke="#76c5e8" strokeLinecap="round">
        {tracks.map((track, index) => (
          <path key={index} d={track} opacity={opacity * (index % 3 === 0 ? 0.82 : 0.46)} strokeWidth={index % 4 === 0 ? 0.8 : 0.55} />
        ))}
      </g>
      <g fill="#c8efff">
        <circle cx="31" cy="29" r="1.15" opacity="0.72" />
        <circle cx="57" cy="104" r="0.9" opacity="0.66" />
        <circle cx="93" cy="42" r="0.8" opacity="0.56" />
        <circle cx="223" cy="99" r="1.1" opacity="0.74" />
        <circle cx="286" cy="68" r="0.9" opacity="0.67" />
      </g>
      <circle cx="164" cy="70" r="37.5" fill="#6cc8f1" opacity={0.28 * ringOpacity} filter={`url(#well-glow-${state.id})`} />
      <circle cx="164" cy="70" r="37" fill={`url(#well-fill-${state.id})`} stroke={`url(#well-ring-${state.id})`} strokeWidth={state.id === "focused" ? 2.2 : 1.7} opacity={ringOpacity} />
      {state.open && (
        <g fill="none" stroke="#8fdcff" strokeWidth="0.75" opacity="0.54">
          <ellipse cx="164" cy="70" rx="27" ry="8" />
          <ellipse cx="164" cy="70" rx="20" ry="5.5" opacity="0.72" />
          <ellipse cx="164" cy="70" rx="12" ry="3.4" opacity="0.55" />
        </g>
      )}
    </svg>
  );
}

export function GravityWellPreviewPage() {
  return (
    <main className="gravity-well-preview">
      <header className="gravity-preview-header">
        <a className="gravity-preview-brand" href="/" aria-label="Life OS home">
          <span className="gravity-preview-brand-mark" aria-hidden="true" />
          <span>Life OS</span>
        </a>
        <div className="gravity-preview-catalog-label"><i /> SYSTEM OBJECT CATALOG</div>
      </header>

      <section className="gravity-preview-hero" aria-label="Gravity Well object overview">
        <div className="gravity-preview-copy">
          <p className="gravity-preview-eyebrow"><i /> SETTINGS</p>
          <h1>Settings Gravity Well</h1>
          <p className="gravity-preview-subtitle">The system substrate beneath Life OS.</p>

          <section className="gravity-preview-spec" aria-labelledby="gravity-role-heading">
            <h2 id="gravity-role-heading">Role</h2>
            <ul>
              <li>Not a planet</li>
              <li>Entry to system configuration</li>
              <li>Sits beneath Self Core at Depth 0</li>
            </ul>
          </section>

          <section className="gravity-preview-spec gravity-preview-motion" aria-labelledby="gravity-motion-heading">
            <h2 id="gravity-motion-heading">Motion</h2>
            <ul>
              <li>Slow lensing distortion</li>
              <li>Delicate warped starflow</li>
              <li>Focus transition falls inward</li>
            </ul>
          </section>
        </div>

        <div className="gravity-preview-stage" aria-label="Hero scale gravity well render">
          <div className="gravity-preview-stage-cross gravity-preview-stage-cross--top" aria-hidden="true" />
          <div className="gravity-preview-stage-cross gravity-preview-stage-cross--bottom" aria-hidden="true" />
          <GravityWellCanvas />
          <div className="gravity-preview-stage-note"><span /> PROCEDURAL / REAL-TIME <i /> NO BAKED BACKGROUND</div>
        </div>
      </section>

      <section className="gravity-preview-states" aria-labelledby="gravity-states-heading">
        <header className="gravity-preview-states-heading">
          <h2 id="gravity-states-heading">States</h2>
          <span />
        </header>
        <div className="gravity-preview-state-grid">
          {states.map((state) => (
            <article className={`gravity-preview-state gravity-preview-state--${state.id}`} key={state.id}>
              <div className="gravity-preview-state-canvas" aria-label={`${state.label} state render`}>
                <GravityWellStateStudy state={state} />
              </div>
              <h3>{state.label}</h3>
              <span className="gravity-preview-state-accent" />
              <p>{state.description}</p>
            </article>
          ))}
        </div>
      </section>
    </main>
  );
}
