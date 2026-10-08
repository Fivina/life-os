import { GRAVITY_SETTINGS_NEAR_STREAM_PATHS } from "./gravity-settings-flow-paths";

export function GravitySettingsNode({ compact = false }: { compact?: boolean }) {
  return (
    <svg className={`gravity-anomaly ${compact ? "compact" : ""}`} viewBox="0 0 130 120" aria-hidden="true">
      <defs>
        <radialGradient id="aperture-depth" cx="48%" cy="48%" r="54%">
          <stop offset="0" stopColor="#000000" />
          <stop offset="0.72" stopColor="#000000" />
          <stop offset="1" stopColor="#000000" />
        </radialGradient>
      </defs>
      <g className="anomaly-near-streams">
        {GRAVITY_SETTINGS_NEAR_STREAM_PATHS.map((path) => <path key={path} d={path} />)}
      </g>
      <g className="anomaly-near-particles">
        <circle cx="6" cy="39" r="0.9" /><circle cx="18" cy="57" r="0.7" />
        <circle cx="28" cy="76" r="1" /><circle cx="43" cy="92" r="0.75" />
        <circle cx="55" cy="104" r="0.9" /><circle cx="84" cy="106" r="0.7" />
        <circle cx="107" cy="94" r="1" /><circle cx="123" cy="77" r="0.75" />
        <circle cx="132" cy="56" r="0.85" /><circle cx="115" cy="39" r="0.65" />
        <circle cx="35" cy="49" r="0.6" /><circle cx="35" cy="84" r="0.7" />
        <circle cx="72" cy="105" r="0.65" /><circle cx="99" cy="101" r="0.75" />
        <path d="M20 68 C26 67 31 66 36 64" />
        <path d="M40 99 C46 101 51 103 57 104" />
        <path d="M100 96 C106 92 111 88 116 84" />
      </g>
      <path className="anomaly-absorption" d="M35 60 C36 41 49 28 66 28 C86 28 98 42 97 61 C96 80 82 93 64 94 C46 94 34 80 35 60 Z" />
      <g className="anomaly-accretion-shell">
        <ellipse className="anomaly-accretion-orbit anomaly-accretion-orbit-a" cx="66" cy="60" rx="34" ry="25" />
        <ellipse className="anomaly-accretion-orbit anomaly-accretion-orbit-b" cx="66" cy="60" rx="31" ry="29" />
        <ellipse className="anomaly-accretion-orbit anomaly-accretion-orbit-c" cx="66" cy="60" rx="38" ry="21" />
      </g>
      <path className="anomaly-aperture" d="M38 60 C39 43 50 32 66 31 C83 31 95 43 94 60 C93 77 81 89 65 90 C49 90 38 78 38 60 Z" fill="url(#aperture-depth)" />
      <path className="anomaly-horizon-glow" d="M38 60 C39 43 50 32 66 31 C83 31 95 43 94 60 C93 77 81 89 65 90 C49 90 38 78 38 60 Z" />
      <path className="anomaly-horizon-ring" d="M38 60 C39 43 50 32 66 31 C83 31 95 43 94 60 C93 77 81 89 65 90 C49 90 38 78 38 60 Z" />
      <path className="anomaly-horizon-flow" d="M38 60 C39 43 50 32 66 31 C83 31 95 43 94 60 C93 77 81 89 65 90 C49 90 38 78 38 60 Z" pathLength="100" />
      <path className="anomaly-horizon-embers" d="M38 60 C39 43 50 32 66 31 C83 31 95 43 94 60 C93 77 81 89 65 90 C49 90 38 78 38 60 Z" pathLength="100" />
      <path className="anomaly-horizon-sparks" d="M38 60 C39 43 50 32 66 31 C83 31 95 43 94 60 C93 77 81 89 65 90 C49 90 38 78 38 60 Z" pathLength="100" />
      <path className="anomaly-rim anomaly-rim-lower" d="M38 68 C41 78 49 86 59 89" />
      <path className="anomaly-rim anomaly-rim-lower-soft" d="M42 75 C48 84 57 89 68 89" />
      <path className="anomaly-rim anomaly-rim-lower-tail" d="M50 84 C59 90 70 89 79 84" />
      <path className="anomaly-rim anomaly-rim-left" d="M40 69 C36 61 38 51 43 44" />
      <path className="anomaly-rim anomaly-rim-glint" d="M45 79 C49 85 54 88 60 89" />
    </svg>
  );
}
