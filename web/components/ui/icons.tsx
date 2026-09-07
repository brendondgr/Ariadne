import type { SVGProps } from "react";

/** Inline icon set matching the mockup's SVGs. Single-color icons inherit
 *  `currentColor`; the multi-color Ariadne thread glyph is self-colored. */

type IconProps = SVGProps<SVGSVGElement> & { size?: number };

function base({ size = 16, ...props }: IconProps) {
  return {
    width: size,
    height: size,
    viewBox: "0 0 24 24",
    fill: "none",
    ...props,
  };
}

export function ThreadGlyph({ size = 22, ...props }: IconProps) {
  return (
    <svg {...base({ size, ...props })} aria-hidden>
      <circle cx="12" cy="12" r="9.2" stroke="#4E9E96" strokeWidth="1.3" opacity="0.5" />
      <path
        d="M12 3.2 C7 7, 17 9, 12 12 C7 15, 17 17, 12 20.8"
        stroke="#EBE6DC"
        strokeWidth="1.4"
        strokeLinecap="round"
      />
      <circle cx="12" cy="12" r="1.7" fill="#C9924A" />
    </svg>
  );
}

export function PlayIcon({ size = 13, ...props }: IconProps) {
  return (
    <svg {...base({ size, ...props })} aria-hidden>
      <path d="M5 3l14 9-14 9V3z" fill="currentColor" />
    </svg>
  );
}

export function UserIcon({ size = 16, ...props }: IconProps) {
  return (
    <svg {...base({ size, ...props })} aria-hidden>
      <path d="M12 11a4 4 0 100-8 4 4 0 000 8z" stroke="currentColor" strokeWidth="1.5" />
      <path d="M5 21a7 7 0 0114 0" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

export function PlusIcon({ size = 11, ...props }: IconProps) {
  return (
    <svg {...base({ size, ...props })} aria-hidden>
      <path d="M12 5v14M5 12h14" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" />
    </svg>
  );
}

export function CheckIcon({ size = 11, ...props }: IconProps) {
  return (
    <svg {...base({ size, ...props })} aria-hidden>
      <path
        d="M5 13l4 4L19 7"
        stroke="currentColor"
        strokeWidth="2.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function ShieldIcon({ size = 10, ...props }: IconProps) {
  return (
    <svg {...base({ size, ...props })} aria-hidden>
      <path
        d="M12 3l7 3v6c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6l7-3z"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function ChevronRight({ size = 13, ...props }: IconProps) {
  return (
    <svg {...base({ size, ...props })} aria-hidden>
      <path
        d="M9 6l6 6-6 6"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function ArrowRight({ size = 26, ...props }: IconProps) {
  return (
    <svg
      width={size}
      height={(size * 14) / 26}
      viewBox="0 0 26 14"
      fill="none"
      aria-hidden
      {...props}
    >
      <path
        d="M2 7h22M19 3l5 4-5 4"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function SendArrow({ size = 13, ...props }: IconProps) {
  return (
    <svg {...base({ size, ...props })} aria-hidden>
      <path
        d="M5 12h14M13 6l6 6-6 6"
        stroke="currentColor"
        strokeWidth="2.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function CopyIcon({ size = 12, ...props }: IconProps) {
  return (
    <svg {...base({ size, ...props })} aria-hidden>
      <rect x="9" y="9" width="11" height="11" rx="2" stroke="currentColor" strokeWidth="1.6" />
      <path d="M5 15V5a2 2 0 012-2h10" stroke="currentColor" strokeWidth="1.6" />
    </svg>
  );
}

export function ExportIcon({ size = 12, ...props }: IconProps) {
  return (
    <svg {...base({ size, ...props })} aria-hidden>
      <path
        d="M12 3v12m0 0l-4-4m4 4l4-4M5 21h14"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function MenuIcon({ size = 18, ...props }: IconProps) {
  return (
    <svg {...base({ size, ...props })} aria-hidden>
      <path d="M4 7h16M4 12h16M4 17h16" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  );
}

export function CloseIcon({ size = 16, ...props }: IconProps) {
  return (
    <svg {...base({ size, ...props })} aria-hidden>
      <path d="M6 6l12 12M18 6L6 18" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
    </svg>
  );
}

/** Settings — a toothed cog.
 *
 *  The outer path is a real gear outline (8 teeth, generated as alternating
 *  tip/root vertices about a 12,12 centre), NOT a circle with radiating rays:
 *  the previous drawing was eight spokes around a hub, which reads as a sun or
 *  a brightness/light-bulb control rather than settings. */
export function GearIcon({ size = 16, ...props }: IconProps) {
  return (
    <svg {...base({ size, ...props })} aria-hidden>
      <path
        d="M10.44 2.12L13.56 2.12L13.64 4.58L16.08 5.59L17.88 3.91L20.09 6.12L18.41 7.92L19.42 10.36L21.88 10.44L21.88 13.56L19.42 13.64L18.41 16.08L20.09 17.88L17.88 20.09L16.08 18.41L13.64 19.42L13.56 21.88L10.44 21.88L10.36 19.42L7.92 18.41L6.12 20.09L3.91 17.88L5.59 16.08L4.58 13.64L2.12 13.56L2.12 10.44L4.58 10.36L5.59 7.92L3.91 6.12L6.12 3.91L7.92 5.59L10.36 4.58Z"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
      <circle cx="12" cy="12" r="3.2" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  );
}

export function LinkIcon({ size = 12, ...props }: IconProps) {
  return (
    <svg {...base({ size, ...props })} aria-hidden>
      <path d="M8 4h9a2 2 0 012 2v12M16 8H7a2 2 0 00-2 2v9" stroke="currentColor" strokeWidth="1.6" />
    </svg>
  );
}

const S = { stroke: "currentColor", strokeWidth: 1.7, strokeLinecap: "round", strokeLinejoin: "round" } as const;

/** Evidence — a document with lines. */
export function EvidenceIcon({ size = 13, ...props }: IconProps) {
  return (
    <svg {...base({ size, ...props })} aria-hidden>
      <path d="M6 3h8l4 4v14H6z" {...S} />
      <path d="M14 3v4h4M9 12h6M9 16h6" {...S} />
    </svg>
  );
}

/** Verified — a shield with a check. */
export function VerifiedIcon({ size = 13, ...props }: IconProps) {
  return (
    <svg {...base({ size, ...props })} aria-hidden>
      <path d="M12 3l7 3v5c0 4.5-3 8-7 10-4-2-7-5.5-7-10V6z" {...S} />
      <path d="M9 12l2 2 4-4" {...S} />
    </svg>
  );
}

/** Claim table — a grid. */
export function TableIcon({ size = 13, ...props }: IconProps) {
  return (
    <svg {...base({ size, ...props })} aria-hidden>
      <rect x="3.5" y="4.5" width="17" height="15" rx="1.5" {...S} />
      <path d="M3.5 10h17M3.5 15h17M10 4.5v15" {...S} />
    </svg>
  );
}

/** Matrix — a coverage grid. */
export function GridIcon({ size = 13, ...props }: IconProps) {
  return (
    <svg {...base({ size, ...props })} aria-hidden>
      <rect x="3.5" y="4.5" width="17" height="15" rx="1.5" {...S} />
      <path d="M3.5 9.5h17M3.5 14.5h17M9 4.5v15M15 4.5v15" {...S} />
    </svg>
  );
}

/** Network plot — connected nodes. */
export function NetworkIcon({ size = 13, ...props }: IconProps) {
  return (
    <svg {...base({ size, ...props })} aria-hidden>
      <path d="M7 7l5 4M17 7l-5 4M12 11v6" {...S} />
      <circle cx="7" cy="6" r="2.2" {...S} />
      <circle cx="17" cy="6" r="2.2" {...S} />
      <circle cx="12" cy="18" r="2.2" {...S} />
    </svg>
  );
}

/** Logs — a terminal / list. */
export function LogsIcon({ size = 13, ...props }: IconProps) {
  return (
    <svg {...base({ size, ...props })} aria-hidden>
      <rect x="3.5" y="4.5" width="17" height="15" rx="1.5" {...S} />
      <path d="M7 9l2.5 2L7 13M12 14h4" {...S} />
    </svg>
  );
}

/** Swirl — a spinning arc. Shown on a sidebar chat whose query is still running
 *  in the background (keeps spinning across chat switches). */
export function SwirlIcon({ size = 13, className, ...props }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      className={`animate-spin${className ? ` ${className}` : ""}`}
      aria-hidden
      {...props}
    >
      <circle cx="12" cy="12" r="8" stroke="currentColor" strokeWidth="2" opacity="0.25" />
      <path d="M12 4a8 8 0 0 1 8 8" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" />
    </svg>
  );
}

/** Rename — a pencil. Used on the sidebar conversation row's rename action. */
export function PencilIcon({ size = 12, ...props }: IconProps) {
  return (
    <svg {...base({ size, ...props })} aria-hidden>
      <path
        d="M15.5 4.5l4 4L8 20H4v-4L15.5 4.5z"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

/** Delete — a trash can. Used on the sidebar conversation row's delete action. */
export function TrashIcon({ size = 12, ...props }: IconProps) {
  return (
    <svg {...base({ size, ...props })} aria-hidden>
      <path
        d="M4 7h16M9 7V4.5h6V7M7 7l1 12.5h8L17 7"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
