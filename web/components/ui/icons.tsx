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

export function LinkIcon({ size = 12, ...props }: IconProps) {
  return (
    <svg {...base({ size, ...props })} aria-hidden>
      <path d="M8 4h9a2 2 0 012 2v12M16 8H7a2 2 0 00-2 2v9" stroke="currentColor" strokeWidth="1.6" />
    </svg>
  );
}
