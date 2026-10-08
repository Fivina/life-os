import type { CSSProperties } from "react";

import type { HubModuleId } from "./hubModules";
import { clickTravelTimes, hoverTravelTimes, type HubEnergyState } from "./useHubEnergy";

type DomainModuleId = Exclude<HubModuleId, "settings">;

type SculptureGeometry = {
  backbone: string;
  filament: string;
  details: string[];
  nodes: Array<[number, number, number]>;
};

type SculptureDefinition = {
  desktop: SculptureGeometry;
  mobile: SculptureGeometry;
};

const sculptures: Record<DomainModuleId, SculptureDefinition> = {
  calendar: {
    desktop: {
      backbone: "M515 350 C452 321 418 231 349 170 C311 136 279 130 247 139 C221 147 200 153 177 154 C154 156 137 154 129 147 C121 140 122 130 128 124 C134 118 141 117 149 119",
      filament: "M511 343 C450 312 422 222 354 162 C315 128 279 123 245 132 C218 140 196 147 173 148 C154 150 142 148 134 143",
      details: ["M149 111 V133 C149 140 154 144 162 144 H195 C203 144 208 140 208 132 V111 M149 111 H158 M166 111 H189 M197 111 H208", "M160 101 C157 103 157 110 160 112 C163 114 165 111 165 108 V98 C165 95 162 94 160 96 V101 M191 101 C188 103 188 110 191 112 C194 114 196 111 196 108 V98 C196 95 193 94 191 96 V101", "M208 111 C223 109 237 106 250 100 C263 94 275 84 286 69"],
      nodes: [[160, 96, 1.65], [191, 96, 1.65], [208, 111, 1.35], [286, 69, 2.05]]
    },
    mobile: {
      backbone: "M510 338 C580 290 647 194 716 151 C746 133 775 128 806 130 C838 132 861 139 883 151",
      filament: "M514 346 C589 300 654 203 721 159 C753 138 785 133 818 136",
      details: ["M738 137 V160 C738 167 744 171 753 171 H837 C846 171 852 167 852 159 V137 M738 137 H759 M768 137 H822 M831 137 H852", "M762 125 C759 128 759 135 762 138 C765 140 768 137 768 133 V121 C768 118 765 116 762 119 V125 M825 125 C822 128 822 135 825 138 C828 140 831 137 831 133 V121 C831 118 828 116 825 119 V125", "M852 137 C879 134 907 124 931 109 C945 100 956 90 966 78"],
      nodes: [[762, 119, 1.65], [825, 119, 1.65], [852, 137, 1.35], [966, 78, 2.05]]
    },
  },
  learning: {
    desktop: {
      backbone: "M493 360 C431 373 382 355 323 314 C280 284 244 270 214 263 C204 261 197 259 200 257 C193 250 192 240 188 232 C182 220 169 217 158 223 C151 212 136 211 128 221 C116 218 105 227 108 238 C99 244 101 256 112 260",
      filament: "M489 368 C429 381 380 365 319 325 C273 294 236 280 205 274 C187 271 172 274 158 282",
      details: ["M112 260 C104 265 106 276 117 278 C124 288 139 287 145 277 C155 284 169 279 171 268 C184 271 195 266 200 257", "M108 238 C119 237 127 243 129 251 C131 259 124 264 116 262", "M117 278 C122 270 131 268 138 272 C143 275 145 279 145 277", "M145 252 C154 248 163 249 171 255 C180 262 190 262 200 257"],
      nodes: [[145, 252, 2], [171, 255, 1.45], [200, 257, 1.7]]
    },
    mobile: {
      backbone: "M492 345 C430 334 391 289 346 245 C319 219 292 208 266 205 C256 203 249 202 251 200 C244 193 244 185 240 178 C234 168 222 166 212 171 C205 162 192 162 185 170 C174 167 165 175 168 184 C159 189 162 199 172 202",
      filament: "M489 354 C427 344 387 301 340 257 C311 230 283 221 258 217 C242 215 228 218 216 225",
      details: ["M172 202 C165 207 168 216 177 218 C184 227 197 226 202 218 C211 224 224 220 226 211 C237 214 247 209 251 200", "M168 184 C178 183 185 188 187 195 C189 202 183 206 176 204", "M177 218 C182 211 190 209 196 213 C200 216 202 219 202 218", "M202 196 C210 193 219 194 226 199 C234 205 242 205 251 200"],
      nodes: [[202, 196, 2], [226, 199, 1.45], [251, 200, 1.7]]
    },
  },
  life: {
    desktop: {
      backbone: "M542 334 C612 289 661 220 729 184 C767 164 804 166 836 151 C865 138 885 115 905 91 C915 81 924 74 933 68",
      filament: "M538 326 C609 278 655 211 724 175 C761 156 800 158 831 145 C854 135 872 118 888 100",
      details: ["M813 160 C836 166 856 160 873 147 C887 136 900 132 914 134", "M838 151 C833 139 825 130 814 123 C807 119 801 115 796 109", "M787 170 C817 180 848 180 878 171 C907 162 935 165 961 176", "M933 68 L926 84 M933 68 L917 75"],
      nodes: [[796, 109, 1.65], [813, 160, 1.4], [873, 147, 1.3], [914, 134, 1.75], [878, 171, 1.3], [961, 176, 2], [933, 68, 2.05]]
    },
    mobile: {
      backbone: "M536 332 C594 313 643 288 700 275 C744 265 779 251 810 229 C832 213 849 194 866 176",
      filament: "M533 324 C592 304 641 279 697 267 C739 258 773 244 802 224",
      details: ["M724 269 C747 276 770 272 791 260 C808 250 825 247 843 251", "M762 258 C756 247 748 238 737 231 C731 227 726 223 722 219", "M701 276 C732 286 765 287 797 280 C823 274 848 277 872 289", "M866 176 L858 190 M866 176 L852 182"],
      nodes: [[722, 219, 1.65], [724, 269, 1.4], [791, 260, 1.3], [843, 251, 1.75], [797, 280, 1.3], [872, 289, 2], [866, 176, 2.05]]
    },
  },
  fitness: {
    desktop: {
      backbone: "M548 365 C625 384 666 433 730 439 C775 443 810 407 845 394 C856 390 865 388 874 388 C874 376 876 367 881 367 C886 367 888 376 888 388 C888 400 886 411 881 411 C876 411 874 400 874 388 L888 388 C908 388 933 388 953 388 C953 376 955 367 960 367 C965 367 967 376 967 388 C967 400 965 411 960 411 C955 411 953 400 953 388 L967 388 C977 388 982 394 989 390 C996 386 1001 378 1005 374",
      filament: "M551 357 C627 375 671 422 731 429 C775 434 808 401 843 386 C860 379 875 379 890 380",
      details: ["M874 388 C874 376 876 367 881 367 C886 367 888 376 888 388 C888 400 886 411 881 411 C876 411 874 400 874 388 M881 373 V405 M953 388 C953 376 955 367 960 367 C965 367 967 376 967 388 C967 400 965 411 960 411 C955 411 953 400 953 388 M960 373 V405", "M869 377 C864 377 862 381 862 385 V397 C862 400 864 402 868 402 M862 385 H858 M972 377 C977 377 979 381 979 385 V397 C979 400 977 402 973 402 M979 385 H983", "M888 383 C908 382 933 382 953 383 M888 394 C908 395 933 395 953 394"],
      nodes: [[845, 394, 1.9], [1005, 374, 2.3]]
    },
    mobile: {
      backbone: "M548 359 C606 376 647 424 691 457 C714 474 735 482 756 482 H783 C783 470 785 461 790 461 C795 461 797 470 797 482 C797 494 795 505 790 505 C785 505 783 494 783 482 L797 482 H907 C907 470 909 461 914 461 C919 461 921 470 921 482 C921 494 919 505 914 505 C909 505 907 494 907 482 L921 482 H946 C963 482 972 491 981 487 C989 484 995 475 1000 468",
      filament: "M552 351 C610 367 651 414 696 447 C718 463 739 471 760 472 C811 474 868 473 920 472",
      details: ["M783 482 C783 470 785 461 790 461 C795 461 797 470 797 482 C797 494 795 505 790 505 C785 505 783 494 783 482 M790 467 V499 M907 482 C907 470 909 461 914 461 C919 461 921 470 921 482 C921 494 919 505 914 505 C909 505 907 494 907 482 M914 467 V499", "M778 471 C773 471 771 475 771 479 V491 C771 494 773 496 777 496 M771 479 H767 M926 471 C931 471 933 475 933 479 V491 C933 494 931 496 927 496 M933 479 H937", "M797 476 C827 475 877 475 907 476 M797 489 C827 490 877 490 907 489"],
      nodes: [[756, 482, 1.9], [1000, 468, 2.3]]
    },
  },
  kitchen: {
    desktop: {
      backbone: "M524 378 C518 432 544 470 539 512 C535 542 506 561 466 576 C453 586 439 598 424 611 C423 627 423 643 424 656 C434 658 444 658 454 658 V630 C460 627 469 627 475 630 V658 C490 658 505 657 518 654 C534 651 545 633 559 621 C571 611 585 614 596 623 C602 628 608 627 614 622",
      filament: "M516 378 C510 432 534 473 530 510 C526 538 501 554 468 568",
      details: ["M466 576 C480 587 494 598 509 611"],
      nodes: [[466, 576, 1.55], [559, 621, 1.65], [614, 622, 2.1]]
    },
    mobile: {
      backbone: "M517 373 C520 438 546 489 535 543 C529 571 495 590 447 610 C415 621 383 631 350 640 C349 651 349 661 350 670 C374 672 401 672 430 671 V650 C439 647 455 647 464 650 V671 C493 670 521 669 548 665 C567 662 583 646 599 632 C613 620 628 622 641 631 C648 636 656 634 663 628",
      filament: "M508 374 C510 440 536 490 525 539 C519 565 489 583 448 601",
      details: ["M447 610 C480 620 513 631 547 641"],
      nodes: [[447, 610, 1.55], [599, 632, 1.65], [663, 628, 2.1]]
    },
  }
};

export function EnergyArm({ id, energy }: { id: DomainModuleId; energy: HubEnergyState }) {
  const sculpture = sculptures[id];
  const targeted = energy.target === id;
  const activated = targeted && ["active", "decay"].includes(energy.phase);
  const duration = energy.mode === "SELECT_MODULE" ? clickTravelTimes[id] : hoverTravelTimes[id];
  const style = { "--target-pulse-duration": `${duration}ms` } as CSSProperties;

  return (
    <g className={`living-arm system-sculpture system-sculpture-${id} phase-${energy.phase} ${targeted ? "targeted" : ""} ${activated ? "activated" : ""}`} data-module={id} style={style}>
      <g className="arm-desktop">
        <SculptureLayers id={id} geometry={sculpture.desktop} energy={energy} targeted={targeted} duration={duration} />
      </g>
      <g className="arm-mobile">
        <SculptureLayers id={id} geometry={sculpture.mobile} energy={energy} targeted={targeted} duration={duration} />
      </g>
    </g>
  );
}

function SculptureLayers({
  id,
  geometry,
  energy,
  targeted,
  duration
}: {
  id: DomainModuleId;
  geometry: SculptureGeometry;
  energy: HubEnergyState;
  targeted: boolean;
  duration: number;
}) {
  const travelling = targeted && energy.phase === "travel";
  const energized = targeted && ["travel", "active", "decay"].includes(energy.phase);

  return (
    <>
      <path className="arm-field sculpture-field" d={geometry.backbone} pathLength="100" />
      <path className="arm-body sculpture-backbone" d={geometry.backbone} pathLength="100" />
      <path className="arm-hot sculpture-hot" d={geometry.backbone} pathLength="100" />
      <path className="arm-filament sculpture-filament" d={geometry.backbone} pathLength="100" />
      <path className="arm-filament sculpture-companion" d={geometry.filament} pathLength="100" />
      <g className="sculpture-details">
        {geometry.details.map((path, index) => <path key={path} className={`sculpture-detail sculpture-detail-${index + 1}`} d={path} pathLength="100" />)}
      </g>
      <g className="sculpture-nodes">
        {geometry.nodes.map(([cx, cy, radius], index) => (
          <circle
            key={`${cx}-${cy}`}
            className={`sculpture-node sculpture-node-${index + 1} ${index === geometry.nodes.length - 1 ? "terminal-node" : ""}`}
            cx={cx}
            cy={cy}
            r={radius}
          />
        ))}
      </g>
      <path className="idle-arm-pulse" d={geometry.backbone} pathLength="100" />
      {energized ? (
        <>
          <path
            key={`halo-${energy.signal}-${energy.phase}`}
            className={`target-energy-halo energy-fill-${energy.phase} ${energy.mode === "SELECT_MODULE" ? "strong" : ""}`}
            d={geometry.backbone}
            pathLength="100"
          />
          <path
            key={`fill-${energy.signal}-${energy.phase}`}
            className={`target-energy-fill energy-fill-${energy.phase} ${energy.mode === "SELECT_MODULE" ? "strong" : ""}`}
            d={geometry.backbone}
            pathLength="100"
          />
          <path
            key={`companion-${energy.signal}-${energy.phase}`}
            className={`target-companion-fill energy-fill-${energy.phase}`}
            d={geometry.filament}
            pathLength="100"
          />
          <g className={`target-detail-system target-detail-system-${id}`}>
            {geometry.details.map((path, index) => (
              <path
                key={`detail-${energy.signal}-${energy.phase}-${index}`}
                className={`target-detail-fill target-detail-${index + 1} energy-fill-${energy.phase}`}
                d={path}
                pathLength="100"
                style={{
                  "--detail-delay": `${Math.round(duration * (0.32 + index * 0.035))}ms`,
                  "--detail-duration": `${Math.round(duration * 0.64)}ms`
                } as CSSProperties}
              />
            ))}
          </g>
          <g className="target-node-system">
            {geometry.nodes.map(([cx, cy, radius], index) => (
              <circle
                key={`node-${energy.signal}-${energy.phase}-${cx}-${cy}`}
                className={`target-node-light node-phase-${energy.phase} ${index === geometry.nodes.length - 1 ? "terminal-node-light" : ""}`}
                cx={cx}
                cy={cy}
                r={radius + (index === geometry.nodes.length - 1 ? 0.7 : 0.25)}
                style={{ "--node-delay": `${Math.round(duration * (0.52 + index * 0.055))}ms` } as CSSProperties}
              />
            ))}
          </g>
        </>
      ) : null}
      {travelling ? (
        <path
          key={`front-${energy.signal}`}
          className={`target-energy-front ${energy.mode === "SELECT_MODULE" ? "strong" : ""}`}
          d={geometry.backbone}
          pathLength="100"
        />
      ) : null}
    </>
  );
}
