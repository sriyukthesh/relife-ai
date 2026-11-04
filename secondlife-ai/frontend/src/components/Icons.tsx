import type { ReactNode } from "react";

/** Small inline icon set (no extra dependency). 24x24, stroke-based. */
function Svg({ children, size = 20, className = "" }: { children: ReactNode; size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className={className}>
      {children}
    </svg>
  );
}
type P = { size?: number; className?: string };

export const IconHome = (p: P) => <Svg {...p}><path d="M3 11l9-7 9 7" /><path d="M5 10v10h14V10" /><path d="M10 20v-6h4v6" /></Svg>;
export const IconBack = (p: P) => <Svg {...p}><path d="M19 12H5M12 19l-7-7 7-7" /></Svg>;
export const IconScan = (p: P) => <Svg {...p}><path d="M4 8V5a1 1 0 011-1h3M16 4h3a1 1 0 011 1v3M20 16v3a1 1 0 01-1 1h-3M8 20H5a1 1 0 01-1-1v-3" /><path d="M7 12h10" /></Svg>;
export const IconParts = (p: P) => <Svg {...p}><rect x="4" y="4" width="16" height="16" rx="2" /><path d="M9 4v3M15 4v3M9 17v3M15 17v3M4 9h3M4 15h3M17 9h3M17 15h3" /></Svg>;
export const IconBulb = (p: P) => <Svg {...p}><path d="M9 18h6M10 21h4" /><path d="M12 3a6 6 0 00-3.5 10.9c.6.5 1 1.2 1 2.1h5c0-.9.4-1.6 1-2.1A6 6 0 0012 3z" /></Svg>;
export const IconWrench = (p: P) => <Svg {...p}><path d="M14.7 6.3a4 4 0 015 5L17 14l-7 7a2.1 2.1 0 01-3-3l7-7 2.7-2.7z" /></Svg>;
export const IconStore = (p: P) => <Svg {...p}><path d="M4 9l1.5-5h13L20 9" /><path d="M4 9a2.7 2.7 0 005.3 0 2.7 2.7 0 005.4 0A2.7 2.7 0 0020 9" /><path d="M5 12v8h14v-8" /></Svg>;
export const IconMic = (p: P) => <Svg {...p}><rect x="9" y="3" width="6" height="11" rx="3" /><path d="M5 11a7 7 0 0014 0M12 18v3" /></Svg>;
export const IconStop = (p: P) => <Svg {...p}><rect x="6" y="6" width="12" height="12" rx="2" /></Svg>;
export const IconSend = (p: P) => <Svg {...p}><path d="M4 12l16-8-6 16-2.5-6.5L4 12z" /></Svg>;
export const IconCamera = (p: P) => <Svg {...p}><path d="M4 8h3l1.5-2h7L17 8h3v11H4z" /><circle cx="12" cy="13" r="3.5" /></Svg>;
export const IconImage = (p: P) => <Svg {...p}><rect x="3" y="5" width="18" height="14" rx="2" /><circle cx="9" cy="10" r="1.6" /><path d="M21 16l-5-5-8 8" /></Svg>;
export const IconClose = (p: P) => <Svg {...p}><path d="M6 6l12 12M18 6L6 18" /></Svg>;
export const IconSpeaker = (p: P) => <Svg {...p}><path d="M4 10v4h4l5 4V6l-5 4H4z" /><path d="M16.5 9a4 4 0 010 6M19 6.5a7.5 7.5 0 010 11" /></Svg>;
export const IconSpeakerOff = (p: P) => <Svg {...p}><path d="M4 10v4h4l5 4V6l-5 4H4z" /><path d="M17 9l4 6M21 9l-4 6" /></Svg>;
export const IconSpark = (p: P) => <Svg {...p}><path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3z" /><path d="M19 17l.8 2.2L22 20l-2.2.8L19 23l-.8-2.2L16 20l2.2-.8L19 17z" /></Svg>;
export const IconSwap = (p: P) => <Svg {...p}><path d="M4 8h13l-3-3M20 16H7l3 3" /></Svg>;
export const IconLogout = (p: P) => <Svg {...p}><path d="M9 4H5v16h4M16 8l4 4-4 4M20 12H9" /></Svg>;
export const IconCheck = (p: P) => <Svg {...p}><path d="M5 12.5l4.5 4.5L19 7" /></Svg>;
export const IconTag = (p: P) => <Svg {...p}><path d="M3 12V4h8l10 10-8 8L3 12z" /><circle cx="8" cy="9" r="1.2" /></Svg>;

export const IconCart = (p: P) => <Svg {...p}><path d="M3 4h2.2l2.1 10.2a1 1 0 001 .8h8.6a1 1 0 001-.8L19.5 8H6.1" /><circle cx="9.5" cy="19" r="1.4" /><circle cx="17" cy="19" r="1.4" /></Svg>;
export const IconLock = (p: P) => <Svg {...p}><rect x="5" y="11" width="14" height="9" rx="2" /><path d="M8 11V8a4 4 0 018 0v3" /></Svg>;
export const IconTrash = (p: P) => <Svg {...p}><path d="M4 7h16M10 11v6M14 11v6M6 7l1 12h10l1-12M9 7V4h6v3" /></Svg>;

export function BrandMark({ size = 28 }: { size?: number }) {
  return (
    <img src="/relife-ai-icon.png" width={size} height={size} alt="" aria-hidden="true" className="shrink-0 rounded-lg object-cover" />
  );
}
