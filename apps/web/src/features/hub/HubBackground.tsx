export function HubBackground() {
  return (
    <div className="organism-background" aria-hidden="true">
      <svg className="field-map" viewBox="0 0 1000 700" preserveAspectRatio="none">
        <path className="gravity-line gravity-line-a" d="M82 386 C231 214 379 181 507 335 C632 485 786 455 934 286" />
        <path className="gravity-line gravity-line-b" d="M33 205 C237 95 404 145 492 319 C580 493 777 554 979 454" />
        <path className="gravity-line gravity-line-c" d="M171 662 C252 523 371 423 496 366 C652 295 804 164 916 25" />
        <path className="gravity-line gravity-line-d" d="M2 545 C179 575 350 495 468 374 C602 237 773 190 998 229" />
        <path className="gravity-line gravity-line-e" d="M-40 331 C154 301 316 348 490 360 C682 374 828 333 1042 295" />
        <path className="gravity-line gravity-line-f" d="M61 701 C218 608 344 562 489 414 C627 273 802 94 1018 81" />
        <g className="field-crosses">
          <path d="M98 132 h12 M104 126 v12" />
          <path d="M273 594 h9 M277.5 589.5 v9" />
          <path d="M708 93 h10 M713 88 v10" />
          <path d="M889 531 h12 M895 525 v12" />
          <path d="M603 584 h8 M607 580 v8" />
        </g>
        <g className="field-stars">
          <circle cx="54" cy="82" r="1.1" />
          <circle cx="132" cy="174" r="0.8" />
          <circle cx="191" cy="42" r="1.35" />
          <circle cx="249" cy="216" r="0.7" />
          <circle cx="303" cy="74" r="0.9" />
          <circle cx="361" cy="622" r="1.1" />
          <circle cx="414" cy="121" r="0.75" />
          <circle cx="467" cy="557" r="0.9" />
          <circle cx="548" cy="69" r="1.1" />
          <circle cx="607" cy="207" r="0.7" />
          <circle cx="674" cy="631" r="1.2" />
          <circle cx="741" cy="103" r="0.85" />
          <circle cx="803" cy="590" r="0.75" />
          <circle cx="861" cy="183" r="1.1" />
          <circle cx="929" cy="396" r="0.8" />
          <circle cx="975" cy="116" r="1.2" />
        </g>
      </svg>
      <span className="depth-particle depth-particle-a" />
      <span className="depth-particle depth-particle-b" />
      <span className="depth-particle depth-particle-c" />
      <span className="depth-particle depth-particle-d" />
      <span className="depth-particle depth-particle-e" />
      <span className="depth-particle depth-particle-f" />
      <span className="depth-particle depth-particle-g" />
      <span className="depth-particle depth-particle-h" />
    </div>
  );
}
