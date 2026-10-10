// Colour tokens copied from turo/ui/style.py (C) and turo/ui/overlay.py (buddy blue, ink pill).
export const C = {
  bg: "#0a101d",
  surface: "#111a2e",
  surfaceHi: "#16223b",
  line: "#1d2a42",
  lineHi: "#2a3c60",
  text: "#e6eaf2",
  soft: "#c3cbd9",
  muted: "#8b97ad",
  faint: "#5d6a82",
  accent: "#4f8ff8",
  accentDeep: "#2f6fe8",
  accentInk: "#bcd4ff",
  accentSoft: "#13213d",
  ok: "#34d399",
  warn: "#fbbf24",
  buddy: "#3b82f6",
  ink: "rgba(15, 23, 42, 0.94)",
} as const;

// Windows 11 dark-mode app chrome for the mock apps.
export const WIN = {
  bg: "#202020",
  side: "#1c1c1c",
  card: "#2b2b2b",
  cardHi: "#323232",
  line: "#3a3a3a",
  text: "#ffffff",
  muted: "#a9a9a9",
  accent: "#4cc2ff",
} as const;

export const FONT = "'Segoe UI Variable Display', 'Segoe UI', sans-serif";
export const MONO = "'Cascadia Mono', Consolas, monospace";
export const BG = `radial-gradient(circle at 88% 0%, #142650 0%, ${C.bg} 55%)`;
