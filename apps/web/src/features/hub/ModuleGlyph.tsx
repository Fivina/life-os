import type { HubModuleId } from "./hubModules";

export function ModuleGlyph({ id, compact = false }: { id: Exclude<HubModuleId, "settings">; compact?: boolean }) {
  const className = `organ-glyph organ-glyph-${id} ${compact ? "compact" : ""}`;
  if (id === "calendar") return <CalendarGlyph className={className} />;
  if (id === "life") return <LifeGlyph className={className} />;
  if (id === "fitness") return <FitnessGlyph className={className} />;
  if (id === "learning") return <LearningGlyph className={className} />;
  return <KitchenGlyph className={className} />;
}

function CalendarGlyph({ className }: { className: string }) {
  return (
    <svg className={className} viewBox="0 0 120 100" aria-hidden="true">
      <g className="glyph-lobe glyph-lobe-a">
        <path className="glyph-root glyph-continuation" d="M120 58 C108 59 100 64 91 68 C77 74 60 76 43 75 C29 74 21 68 22 59 C23 52 29 48 36 49" />
        <path className="glyph-primary" d="M40 44 V63 C40 69 44 72 50 72 H85 C91 72 95 69 95 63 V44" />
        <path className="glyph-binding" d="M51 34 C48 36 48 42 51 44 C54 46 56 43 56 40 V31 C56 28 53 27 51 29 V34 M80 34 C77 36 77 42 80 44 C83 46 85 43 85 40 V31 C85 28 82 27 80 29 V34" />
        <path className="glyph-secondary" d="M95 44 C103 42 110 38 117 32" />
      </g>
    </svg>
  );
}

function LifeGlyph({ className }: { className: string }) {
  return (
    <svg className={className} viewBox="0 0 120 100" aria-hidden="true">
      <g className="glyph-lobe glyph-lobe-b">
        <path className="glyph-root glyph-continuation" d="M0 68 C16 68 28 65 39 58 C53 49 63 40 73 33 C82 26 90 20 99 16" />
        <path className="glyph-secondary" d="M39 58 C39 47 34 39 24 32 M53 49 C65 51 77 47 88 39 M65 39 C59 32 54 25 46 20 M49 53 C64 58 79 59 94 55" />
        <path className="glyph-fiber" d="M41 66 C60 61 76 51 88 39 M48 57 C41 51 34 46 25 44" />
        <path className="glyph-tip" d="M99 16 L91 28 M99 16 L86 20" />
      </g>
      <g className="glyph-nodes">
        <circle cx="39" cy="58" r="2.2" />
        <circle cx="73" cy="33" r="2.2" />
        <circle cx="24" cy="32" r="2" />
        <circle cx="88" cy="39" r="2.3" />
        <circle cx="94" cy="55" r="1.8" />
      </g>
    </svg>
  );
}

function FitnessGlyph({ className }: { className: string }) {
  return (
    <svg className={className} viewBox="0 0 120 100" aria-hidden="true">
      <g className="glyph-lobe glyph-lobe-a">
        <path className="glyph-root glyph-continuation" d="M0 53 C13 53 22 52 31 51 H92 C103 51 109 55 120 58" />
        <path className="glyph-primary" d="M31 31 C26 31 24 35 24 40 V64 C24 69 26 73 31 73 C36 73 38 69 38 64 V40 C38 35 36 31 31 31 Z M91 31 C86 31 84 35 84 40 V64 C84 69 86 73 91 73 C96 73 98 69 98 64 V40 C98 35 96 31 91 31 Z" />
        <path className="glyph-secondary" d="M19 39 C15 39 13 43 13 47 V59 C13 62 15 64 18 64 M13 47 H9 M103 39 C107 39 109 43 109 47 V59 C109 62 107 64 104 64 M109 47 H113" />
        <path className="glyph-fiber" d="M39 46 H83 M39 57 H83" />
      </g>
    </svg>
  );
}

function LearningGlyph({ className }: { className: string }) {
  return (
    <svg className={className} viewBox="0 0 120 100" aria-hidden="true">
      <g className="glyph-lobe glyph-lobe-c">
        <path className="glyph-root glyph-continuation" d="M120 58 C108 58 100 60 92 65 C84 70 77 72 69 71 C65 79 55 82 48 76 C39 79 32 73 34 65 C26 60 29 51 37 48 C35 39 45 33 53 37 C59 29 71 30 75 39 C85 37 93 45 90 54 C95 59 93 64 92 65" />
        <path className="glyph-primary" d="M53 37 C50 45 53 53 61 57 C67 61 74 61 81 58" />
        <path className="glyph-secondary" d="M37 48 C45 48 51 53 52 60 C54 67 50 73 48 76 M34 65 C42 61 50 63 55 69 M75 39 C71 46 73 53 81 58" />
        <path className="glyph-fiber" d="M48 58 C58 54 68 54 78 58" />
      </g>
      <g className="glyph-nodes">
        <circle cx="61" cy="57" r="2.1" />
        <circle cx="81" cy="58" r="1.8" />
      </g>
    </svg>
  );
}

function KitchenGlyph({ className }: { className: string }) {
  return (
    <svg className={className} viewBox="0 0 120 100" aria-hidden="true">
      <g className="glyph-lobe glyph-lobe-b">
        <path className="glyph-root glyph-continuation" d="M60 0 C60 12 60 20 60 28 L22 55 V84 C31 86 40 86 48 86 V66 C54 63 64 63 70 66 V86 C83 86 95 84 104 78 C110 74 115 75 120 79" />
        <path className="glyph-primary" d="M60 28 L98 55" />
        <path className="glyph-secondary" d="M22 55 C36 45 48 36 60 28" />
      </g>
    </svg>
  );
}
