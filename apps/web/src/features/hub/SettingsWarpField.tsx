const directionalStreams = [
  "M-90 409 C-18 425 24 442 48 463 C61 474 61 487 50 499 C38 512 37 527 50 541 C72 565 120 574 203 561",
  "M-94 432 C-21 439 22 452 46 470 C59 480 58 493 46 505 C34 518 35 533 51 546 C77 568 128 570 216 545",
  "M-96 456 C-25 454 19 462 43 477 C56 485 55 498 43 510 C31 522 34 538 52 550 C82 569 138 562 228 526",
  "M-98 481 C-29 471 15 472 40 483 C54 489 54 502 42 514 C31 526 35 541 55 552 C88 569 146 551 238 505",
  "M-94 507 C-29 486 13 481 39 488 C54 492 56 504 45 517 C35 529 40 544 61 552 C96 565 155 538 244 483",
  "M-84 535 C-27 502 11 489 38 491 C54 492 59 503 50 516 C41 529 47 543 68 549 C105 560 162 525 245 460",
  "M-69 564 C-21 521 13 496 39 494 C55 492 62 502 55 515 C48 529 55 542 76 545 C113 551 168 511 240 438",
  "M-48 593 C-10 542 19 505 43 497 C58 492 67 500 62 514 C57 528 65 540 86 540 C123 540 174 496 229 418",
  "M-20 621 C8 562 31 514 50 502 C63 494 73 500 70 514 C67 529 77 538 97 536 C133 532 179 482 213 403",
  "M14 643 C31 581 45 526 60 507 C71 495 82 500 82 514 C82 529 93 536 112 531 C146 522 182 468 192 394"
];

const nearTangentialStreams = [
  "M-34 443 C8 447 38 460 51 477 C62 491 57 503 46 514 C35 525 38 540 54 551 C78 568 114 568 166 551",
  "M-39 456 C5 458 35 468 48 483 C59 496 54 508 43 519 C32 531 37 545 55 555 C81 570 120 567 176 545",
  "M-42 470 C1 468 31 476 45 489 C56 500 51 512 40 524 C30 536 36 549 56 558 C84 571 126 565 187 537",
  "M-43 485 C-1 477 28 482 42 494 C53 503 49 516 39 528 C30 539 37 552 58 560 C88 571 133 560 197 527",
  "M-40 501 C0 486 27 487 41 497 C52 505 49 519 40 530 C32 541 40 553 61 559 C93 568 139 552 204 516",
  "M-34 518 C3 496 29 491 43 499 C54 505 52 519 44 531 C37 542 45 553 66 557 C99 564 145 543 208 503",
  "M-25 536 C8 507 32 498 47 502 C58 505 58 519 51 531 C45 542 54 551 74 554 C107 557 152 531 207 488",
  "M-13 554 C15 518 37 504 52 504 C64 504 67 517 61 530 C56 541 65 550 85 550 C117 549 159 518 202 472",
  "M2 573 C25 530 44 510 59 507 C71 504 76 516 72 529 C68 541 78 548 97 546 C128 542 166 506 193 456",
  "M20 591 C37 544 52 516 66 509 C77 504 84 514 82 527 C80 539 91 546 109 541 C139 533 171 494 181 442"
];

const compressedStreams = [
  "M-18 454 C17 457 40 466 50 480 C59 492 54 503 45 513 C36 524 39 537 54 547 C74 561 101 563 139 554",
  "M-22 469 C14 470 37 477 47 489 C56 499 51 510 42 520 C33 531 38 543 54 551 C76 562 105 560 146 546",
  "M-23 484 C12 480 35 485 45 495 C54 504 49 515 41 525 C33 535 39 546 56 553 C79 562 110 556 153 536",
  "M-21 499 C13 489 34 490 45 499 C53 506 50 518 42 528 C35 538 42 548 59 553 C83 560 115 550 158 524",
  "M-16 514 C16 498 37 494 47 501 C56 507 54 519 47 529 C40 539 47 548 65 551 C89 556 121 542 161 511",
  "M-8 530 C21 508 41 500 51 504 C60 508 60 520 54 530 C48 540 56 548 74 549 C98 551 128 532 160 496",
  "M3 546 C28 519 47 506 57 506 C67 506 70 518 65 529 C60 539 69 546 87 545 C111 542 138 518 156 480",
  "M17 561 C38 529 54 511 64 509 C74 507 79 518 75 528 C72 538 81 544 99 541 C123 536 146 506 149 464"
];

const pulseStreams = [directionalStreams[1], directionalStreams[4], directionalStreams[7], nearTangentialStreams[1], nearTangentialStreams[5], compressedStreams[2], compressedStreams[6]];

function StreamField({ transform }: { transform?: string }) {
  return (
    <>
      <g className="settings-warp-lines" transform={transform}>
        {directionalStreams.map((stream) => <path key={stream} d={stream} />)}
      </g>
      <g className="settings-warp-near-lines" transform={transform}>
        {nearTangentialStreams.map((stream) => <path key={stream} d={stream} />)}
      </g>
      <g className="settings-warp-compressed-lines" transform={transform}>
        {compressedStreams.map((stream) => <path key={stream} d={stream} />)}
      </g>
      <g className="settings-infall-pulses" transform={transform}>
        {pulseStreams.map((stream, index) => <path key={`${stream}-${index}`} d={stream} pathLength="100" />)}
      </g>
      <g className="settings-infall-particles" transform={transform}>
        <circle r="1"><animateMotion dur="11s" begin="-3s" repeatCount="indefinite" path={nearTangentialStreams[1]} /></circle>
        <circle r="0.75"><animateMotion dur="14s" begin="-9s" repeatCount="indefinite" path={compressedStreams[3]} /></circle>
        <circle r="0.9"><animateMotion dur="17s" begin="-6s" repeatCount="indefinite" path={directionalStreams[7]} /></circle>
        <circle r="0.65"><animateMotion dur="9s" begin="-7s" repeatCount="indefinite" path={compressedStreams[6]} /></circle>
      </g>
      <g className="settings-warp-points" transform={transform}>
        <circle cx="-4" cy="436" r="0.8" /><circle cx="18" cy="458" r="0.65" />
        <circle cx="31" cy="481" r="0.9" /><circle cx="41" cy="501" r="0.7" />
        <circle cx="48" cy="522" r="0.85" /><circle cx="57" cy="546" r="0.65" />
        <circle cx="78" cy="563" r="0.8" /><circle cx="108" cy="566" r="0.6" />
        <circle cx="139" cy="553" r="0.9" /><circle cx="167" cy="531" r="0.7" />
        <circle cx="193" cy="500" r="0.8" /><circle cx="214" cy="469" r="0.6" />
        <circle cx="227" cy="438" r="0.85" /><circle cx="173" cy="420" r="0.65" />
      </g>
    </>
  );
}

export function SettingsWarpField() {
  return (
    <svg className="settings-warp-field" viewBox="0 0 1000 700" preserveAspectRatio="none" aria-hidden="true">
      <defs>
        <radialGradient id="settings-warp-veil" cx="50%" cy="50%" r="50%">
          <stop offset="0" stopColor="#000208" stopOpacity="0.94" />
          <stop offset="0.28" stopColor="#000715" stopOpacity="0.54" />
          <stop offset="0.7" stopColor="#01091a" stopOpacity="0.16" />
          <stop offset="1" stopColor="#01091a" stopOpacity="0" />
        </radialGradient>
      </defs>
      <g className="settings-warp settings-warp-desktop">
        <ellipse className="settings-warp-veil" cx="80" cy="504" rx="162" ry="142" fill="url(#settings-warp-veil)" />
        <StreamField />
      </g>
      <g className="settings-warp settings-warp-mobile">
        <ellipse className="settings-warp-veil" cx="130" cy="511" rx="152" ry="132" fill="url(#settings-warp-veil)" />
        <StreamField transform="translate(50 7)" />
      </g>
    </svg>
  );
}
