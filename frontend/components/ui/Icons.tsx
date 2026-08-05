import type { SVGProps } from "react";

const base = {
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.4,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  viewBox: "0 0 24 24",
};

type P = SVGProps<SVGSVGElement>;

export const IconWhatsApp = (p: P) => (
  <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden {...p}>
    <path d="M17.47 14.38c-.3-.15-1.75-.86-2.02-.96-.27-.1-.47-.15-.66.15-.2.3-.76.96-.94 1.16-.17.2-.35.22-.64.08-.3-.15-1.25-.46-2.38-1.47-.88-.78-1.47-1.75-1.65-2.05-.17-.3-.02-.46.13-.6.13-.14.3-.35.45-.53.15-.18.2-.3.3-.5.1-.2.05-.38-.02-.53-.08-.15-.66-1.6-.9-2.19-.24-.57-.48-.5-.66-.5h-.56c-.2 0-.52.07-.79.37-.27.3-1.04 1.01-1.04 2.47s1.07 2.86 1.22 3.06c.15.2 2.1 3.2 5.08 4.49.71.3 1.26.49 1.69.63.71.22 1.36.19 1.87.12.57-.09 1.75-.72 2-1.41.25-.7.25-1.29.17-1.41-.07-.13-.27-.2-.56-.35Z" />
    <path d="M12.04 2C6.6 2 2.18 6.42 2.18 11.86c0 1.74.46 3.44 1.32 4.94L2 22l5.36-1.4a9.82 9.82 0 0 0 4.68 1.19h.01c5.43 0 9.85-4.42 9.85-9.86 0-2.63-1.02-5.11-2.88-6.97A9.79 9.79 0 0 0 12.04 2Zm0 17.94h-.01a8.2 8.2 0 0 1-4.17-1.14l-.3-.18-3.1.81.83-3.02-.2-.31a8.13 8.13 0 0 1-1.25-4.34c0-4.52 3.68-8.2 8.2-8.2a8.15 8.15 0 0 1 8.19 8.2c0 4.52-3.68 8.18-8.19 8.18Z" />
  </svg>
);

export const IconTelegram = (p: P) => (
  <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden {...p}>
    <path d="M21.94 4.3 18.9 19.1c-.23 1.02-.84 1.27-1.7.79l-4.7-3.47-2.27 2.19c-.25.25-.46.46-.95.46l.34-4.8 8.75-7.9c.38-.34-.08-.53-.59-.19l-10.8 6.8-4.65-1.46c-1.01-.32-1.03-1.01.21-1.5l18.2-7.02c.84-.31 1.58.2 1.2 1.3Z" />
  </svg>
);

export const IconPhone = (p: P) => (
  <svg {...base} aria-hidden {...p}>
    <path d="M4 5.5C4 4.67 4.67 4 5.5 4h2.06c.6 0 1.13.4 1.3.98l.85 3a1.36 1.36 0 0 1-.4 1.4l-1.2 1.05a12.6 12.6 0 0 0 5.46 5.46l1.05-1.2a1.36 1.36 0 0 1 1.4-.4l3 .85c.58.17.98.7.98 1.3v2.06c0 .83-.67 1.5-1.5 1.5A15.5 15.5 0 0 1 4 5.5Z" />
  </svg>
);

export const IconPin = (p: P) => (
  <svg {...base} aria-hidden {...p}>
    <path d="M12 21s7-5.5 7-10.5A7 7 0 0 0 5 10.5C5 15.5 12 21 12 21Z" />
    <circle cx="12" cy="10.5" r="2.5" />
  </svg>
);

export const IconMail = (p: P) => (
  <svg {...base} aria-hidden {...p}>
    <rect x="3" y="5" width="18" height="14" rx="2.5" />
    <path d="m3.5 7 7.6 5.3a1.6 1.6 0 0 0 1.8 0L20.5 7" />
  </svg>
);

export const IconClock = (p: P) => (
  <svg {...base} aria-hidden {...p}>
    <circle cx="12" cy="12" r="8.5" />
    <path d="M12 7.5V12l3 1.8" />
  </svg>
);

export const IconArrow = (p: P) => (
  <svg {...base} aria-hidden {...p}>
    <path d="M5 12h14M13 6l6 6-6 6" />
  </svg>
);

export const IconClose = (p: P) => (
  <svg {...base} aria-hidden {...p}>
    <path d="m6 6 12 12M18 6 6 18" />
  </svg>
);

export const IconMenu = (p: P) => (
  <svg {...base} aria-hidden {...p}>
    <path d="M4 7h16M4 12h16M4 17h16" />
  </svg>
);

/* --- иконки удобств --- */

export const IconBreakfast = (p: P) => (
  <svg {...base} aria-hidden {...p}>
    <path d="M4 10h11v4a4 4 0 0 1-4 4H8a4 4 0 0 1-4-4v-4Z" />
    <path d="M15 11h2.5a2.5 2.5 0 0 1 0 5H15" />
    <path d="M7 6.5c0-.8.8-1 .8-1.8M10.5 6.5c0-.8.8-1 .8-1.8M3 21h14" />
  </svg>
);

export const IconReception = (p: P) => (
  <svg {...base} aria-hidden {...p}>
    <path d="M3 17h18M5 17a7 7 0 0 1 14 0" />
    <path d="M12 6.5V5M10.5 5h3" />
    <path d="M3 20h18" />
  </svg>
);

export const IconWifi = (p: P) => (
  <svg {...base} aria-hidden {...p}>
    <path d="M2.5 9a14 14 0 0 1 19 0M5.5 12.3a9.6 9.6 0 0 1 13 0M8.7 15.6a5 5 0 0 1 6.6 0" />
    <circle cx="12" cy="19" r="1" fill="currentColor" />
  </svg>
);

export const IconClimate = (p: P) => (
  <svg {...base} aria-hidden {...p}>
    <rect x="3" y="4.5" width="18" height="7" rx="2" />
    <path d="M7 15c0 1.5 1 1.5 1 3M12 15c0 1.5 1 1.5 1 3M17 15c0 1.5 1 1.5 1 3" />
  </svg>
);

export const IconSafe = (p: P) => (
  <svg {...base} aria-hidden {...p}>
    <rect x="3.5" y="4.5" width="17" height="15" rx="2" />
    <circle cx="11" cy="12" r="3.2" />
    <path d="M17 9v6" />
  </svg>
);

export const IconCard = (p: P) => (
  <svg {...base} aria-hidden {...p}>
    <rect x="2.5" y="5.5" width="19" height="13" rx="2.5" />
    <path d="M2.5 10h19M6 15h3" />
  </svg>
);

export const IconClean = (p: P) => (
  <svg {...base} aria-hidden {...p}>
    <path d="M8 3.5 6.5 10h11L16 3.5z" />
    <path d="M6.5 10 5 20.5h14L17.5 10" />
    <path d="M9.5 14v3M14.5 14v3" />
  </svg>
);

export const IconTransfer = (p: P) => (
  <svg {...base} aria-hidden {...p}>
    <path d="M4 16.5V12l1.8-4.2A2 2 0 0 1 7.6 6.5h8.8a2 2 0 0 1 1.8 1.3L20 12v4.5" />
    <path d="M4 12h16" />
    <circle cx="7.5" cy="16.5" r="1.6" />
    <circle cx="16.5" cy="16.5" r="1.6" />
  </svg>
);

export const IconCube = (p: P) => (
  <svg {...base} aria-hidden {...p}>
    <path d="M12 3 20 7.5v9L12 21l-8-4.5v-9L12 3Z" />
    <path d="M12 12 20 7.5M12 12v9M12 12 4 7.5" />
  </svg>
);

export const amenityIcons: Record<string, (p: P) => React.ReactElement> = {
  breakfast: IconBreakfast,
  reception: IconReception,
  wifi: IconWifi,
  climate: IconClimate,
  safe: IconSafe,
  card: IconCard,
  clean: IconClean,
  transfer: IconTransfer,
};
