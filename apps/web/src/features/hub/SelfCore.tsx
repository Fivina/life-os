const orbitA = "M28 132 C48 91 96 72 151 78 C207 84 239 110 231 141 C221 177 173 193 117 184 C64 176 17 157 28 132 Z";
const orbitB = "M72 34 C112 52 162 102 187 157 C208 203 193 228 164 218 C124 204 75 153 53 99 C36 58 45 23 72 34 Z";
const orbitC = "M194 42 C214 65 195 116 153 164 C113 210 69 232 52 207 C34 181 57 130 97 85 C136 42 176 21 194 42 Z";
const orbitD = "M20 91 C57 47 121 25 185 49 C241 70 257 118 229 169 C201 220 135 244 73 219 C18 197 -12 145 20 91 Z";
const orbitE = "M58 145 C68 111 104 92 143 96 C183 100 210 124 202 151 C193 181 156 196 117 189 C78 182 49 169 58 145 Z";
const orbitF = "M39 172 C75 199 141 203 192 171 C231 146 237 108 211 87 C177 59 111 62 65 91 C25 116 13 151 39 172 Z";
const orbitG = "M116 18 C148 31 178 72 187 121 C197 174 180 223 147 239 C118 253 92 223 83 176 C73 126 83 72 103 34 C108 25 112 20 116 18 Z";
const orbitH = "M35 71 C72 46 130 45 178 67 C224 88 246 126 226 158 C205 192 153 205 103 190 C55 176 21 143 23 105 C24 91 28 79 35 71 Z";
const orbitI = "M83 111 C101 89 137 83 164 101 C190 118 188 148 164 165 C139 183 101 176 84 153 C73 138 73 123 83 111 Z";
const orbitJ = "M109 70 C135 82 155 108 158 137 C161 166 145 192 123 194 C102 195 91 168 96 139 C100 112 101 82 109 70 Z";

export function SelfCore({
  onActivate,
  onHoverStart,
  onHoverEnd,
  selected
}: {
  onActivate: (element: HTMLButtonElement) => void;
  onHoverStart: () => void;
  onHoverEnd: () => void;
  selected: boolean;
}) {
  return (
    <button
      className={`organism-core orbital-core ${selected ? "selected" : ""}`}
      type="button"
      aria-label="Open Self Core"
      onClick={(event) => onActivate(event.currentTarget)}
      onMouseEnter={onHoverStart}
      onMouseLeave={onHoverEnd}
      onFocus={onHoverStart}
      onBlur={onHoverEnd}
    >
      <svg className="core-reactor" viewBox="0 0 260 260" aria-hidden="true">
        <defs>
          <radialGradient id="nucleus-corona" cx="50%" cy="50%" r="50%">
            <stop offset="0" stopColor="#ffffff" stopOpacity="1" />
            <stop offset="0.13" stopColor="#dff9ff" stopOpacity="0.96" />
            <stop offset="0.38" stopColor="#42c5ff" stopOpacity="0.55" />
            <stop offset="1" stopColor="#0875bd" stopOpacity="0" />
          </radialGradient>
          <linearGradient id="orbit-depth" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor="#167cbf" stopOpacity="0.12" />
            <stop offset="0.48" stopColor="#79dcff" stopOpacity="0.7" />
            <stop offset="1" stopColor="#dffaff" stopOpacity="0.18" />
          </linearGradient>
          <radialGradient id="nucleus-bloom" cx="50%" cy="50%" r="50%">
            <stop offset="0" stopColor="#d8f8ff" stopOpacity="0.42" />
            <stop offset="0.28" stopColor="#41c8ff" stopOpacity="0.2" />
            <stop offset="1" stopColor="#0875bd" stopOpacity="0" />
          </radialGradient>
          <filter id="core-line-glow" x="-35%" y="-35%" width="170%" height="170%">
            <feGaussianBlur stdDeviation="1.4" />
          </filter>
          <filter id="core-node-glow" x="-300%" y="-300%" width="700%" height="700%">
            <feGaussianBlur in="SourceGraphic" stdDeviation="2.2" result="blur" />
            <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
        </defs>

        <g className="orbit-glow-layer" filter="url(#core-line-glow)">
          {[orbitA, orbitC, orbitE, orbitG, orbitI].map((orbit) => (
            <path key={orbit} d={orbit} />
          ))}
        </g>

        <g className="orbit-depth-back">
          <path className="orbit-route orbit-route-calendar orbit-route-a" d={orbitA} pathLength="100" />
          <path className="orbit-route orbit-route-learning orbit-route-b" d={orbitB} pathLength="100" />
          <path className="orbit-route orbit-route-life orbit-route-c" d={orbitC} pathLength="100" />
          <path className="orbit-route orbit-route-fitness orbit-route-d" d={orbitD} pathLength="100" />
          <path className="orbit-route orbit-route-kitchen orbit-route-e" d={orbitE} pathLength="100" />
          <path className="orbit-route orbit-route-ambient orbit-route-f" d={orbitF} pathLength="100" />
          <path className="orbit-route orbit-route-ambient orbit-route-g" d={orbitG} pathLength="100" />
          <path className="orbit-route orbit-route-ambient orbit-route-h" d={orbitH} pathLength="100" />
          <path className="orbit-route orbit-route-ambient orbit-route-i" d={orbitI} pathLength="100" />
          <path className="orbit-route orbit-route-ambient orbit-route-j" d={orbitJ} pathLength="100" />
        </g>

        <g className="orbit-packets">
          <g className="orbit-packet orbit-packet-a">
            <path d="M-4 0 H4" />
            <animateMotion dur="9.5s" repeatCount="indefinite" path={orbitE} rotate="auto" />
          </g>
          <g className="orbit-packet orbit-packet-b">
            <rect x="-3" y="-1" width="6" height="2" rx="1" />
            <animateMotion dur="14.6s" begin="-4s" repeatCount="indefinite" path={orbitA} rotate="auto" />
          </g>
          <g className="orbit-packet orbit-packet-c">
            <path d="M-5 0 H5" />
            <animateMotion dur="19.8s" begin="-9s" repeatCount="indefinite" path={orbitC} rotate="auto" />
          </g>
          <g className="orbit-packet orbit-packet-d">
            <rect x="-2" y="-1" width="4" height="2" rx="0.8" />
            <animateMotion dur="24s" begin="-13s" repeatCount="indefinite" path={orbitD} rotate="auto" />
          </g>
          <g className="orbit-packet orbit-packet-e">
            <path d="M-3 0 H3" />
            <animateMotion dur="17.2s" begin="-7s" repeatCount="indefinite" path={orbitB} rotate="auto" />
          </g>
        </g>

        <g className="nucleus-system">
          <circle className="nucleus-bloom" cx="130" cy="132" r="44" fill="url(#nucleus-bloom)" />
          <circle className="nucleus-corona" cx="130" cy="132" r="17" fill="url(#nucleus-corona)" />
          <circle className="nucleus-hot-halo" cx="130" cy="132" r="7" />
          <circle className="nucleus-hot" cx="130" cy="132" r="3.6" />
          <circle className="nucleus-wave" cx="130" cy="132" r="9" />
        </g>

        <g className="orbit-depth-front">
          <path className="orbit-route orbit-foreground orbit-route-a" d={orbitA} pathLength="100" />
          <path className="orbit-route orbit-foreground orbit-route-c" d={orbitC} pathLength="100" />
          <path className="orbit-route orbit-foreground orbit-route-e" d={orbitE} pathLength="100" />
          <path className="orbit-route orbit-foreground orbit-route-g" d={orbitG} pathLength="100" />
          <path className="orbit-route orbit-foreground orbit-route-i" d={orbitI} pathLength="100" />
          <path className="orbit-route orbit-foreground orbit-route-j" d={orbitJ} pathLength="100" />
        </g>

        <g className="orbit-stars" filter="url(#core-node-glow)">
          <circle cx="84" cy="83" r="1.7" />
          <circle cx="177" cy="76" r="1.9" />
          <circle cx="211" cy="132" r="1.45" />
          <circle cx="174" cy="190" r="1.6" />
          <circle cx="77" cy="181" r="1.35" />
          <circle cx="130" cy="24" r="1.15" />
          <circle cx="222" cy="171" r="1.25" />
          <circle cx="148" cy="231" r="1.65" />
          <circle cx="67" cy="58" r="1.05" />
          <circle cx="102" cy="101" r="1.25" />
          <circle cx="159" cy="105" r="1.5" />
          <circle cx="156" cy="164" r="1.15" />
        </g>

      </svg>
      <span className="hub-tooltip">Self Core</span>
    </button>
  );
}

export function SelfCoreMark() {
  return (
    <svg className="core-mark" viewBox="0 0 64 64" aria-hidden="true">
      <path className="core-mark-orbit" d="M8 33 C14 18 45 14 56 29 C64 41 48 51 30 49 C14 47 4 41 8 33 Z" />
      <path className="core-mark-orbit" d="M22 8 C37 15 48 37 42 52 C36 62 23 49 17 34 C12 20 13 4 22 8 Z" />
      <circle className="core-mark-source" cx="32" cy="33" r="5" />
    </svg>
  );
}
