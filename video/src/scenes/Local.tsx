import React from "react";
import { Scene } from "../components/Scene";
import { useEnter } from "../components/TuroPanel";
import { C } from "../theme";

const icon = { width: 84, height: 84, fill: "none", stroke: C.accent, strokeWidth: 2, strokeLinecap: "round" } as const;

const WifiOff: React.FC = () => (
  <svg {...icon} viewBox="0 0 24 24">
    <path d="M2 8.8a15 15 0 0 1 20 0M5 12.5a10 10 0 0 1 14 0M8.5 16a5 5 0 0 1 7 0" />
    <circle cx="12" cy="19.5" r="1" fill={C.accent} />
    <path d="M3 3l18 18" stroke={C.warn} />
  </svg>
);

const Lock: React.FC = () => (
  <svg {...icon} viewBox="0 0 24 24">
    <rect x="5" y="11" width="14" height="10" rx="2" />
    <path d="M8 11V7a4 4 0 0 1 8 0v4" />
  </svg>
);

const Peso: React.FC = () => (
  <div style={{ height: 84, fontSize: 76, fontWeight: 800, color: C.accent, lineHeight: "84px" }}>₱0</div>
);

const TILES: [React.ReactNode, string, string][] = [
  [<WifiOff key="w" />, "Works offline", "Wi-Fi off? Turo still works."],
  [<Lock key="l" />, "Private", "Nothing leaves your PC."],
  [<Peso key="p" />, "No cloud bills", "Every question is free."],
];

const MODELS = ["Qwen3-VL 4B · sees", "Parakeet · listens", "Kokoro · speaks", "UI Automation · points"];

const Tile: React.FC<{ i: number; children: React.ReactNode; title: string; sub: string }> = ({ i, children, title, sub }) => (
  <div
    style={{
      ...useEnter(24 + i * 14),
      width: 500,
      height: 300,
      borderRadius: 26,
      padding: "36px 40px",
      background: `linear-gradient(${C.surface}, #0f182a)`,
      border: `2px solid ${C.line}`,
      borderTop: `2px solid #273a5c`,
    }}
  >
    {children}
    <div style={{ fontSize: 46, fontWeight: 700, marginTop: 22 }}>{title}</div>
    <div style={{ fontSize: 30, color: C.soft, marginTop: 8 }}>{sub}</div>
  </div>
);

const Chip: React.FC<{ i: number; text: string }> = ({ i, text }) => (
  <div
    style={{
      ...useEnter(80 + i * 8),
      background: C.accentSoft,
      color: C.accentInk,
      border: "2px solid #24406e",
      borderRadius: 99,
      padding: "12px 26px",
      fontSize: 28,
      fontWeight: 600,
    }}
  >
    {text}
  </div>
);

// Everything runs locally: offline, private, free per question.
export const Local: React.FC = () => (
  <Scene vo="local">
    <div style={{ position: "absolute", top: 110, width: "100%", textAlign: "center" }}>
      <div style={{ fontSize: 120, fontWeight: 800, ...useEnter(2) }}>Runs on your laptop.</div>
    </div>
    <div style={{ position: "absolute", top: 380, width: "100%", display: "flex", justifyContent: "center", gap: 50 }}>
      {TILES.map(([ic, title, sub], i) => (
        <Tile key={title} i={i} title={title} sub={sub}>
          {ic}
        </Tile>
      ))}
    </div>
    <div style={{ position: "absolute", top: 800, width: "100%", display: "flex", justifyContent: "center", gap: 20 }}>
      {MODELS.map((m, i) => (
        <Chip key={m} i={i} text={m} />
      ))}
    </div>
  </Scene>
);
