import React from "react";
import { WIN } from "../theme";

export const TITLE_H = 56;

// A Windows 11 dark-mode app window frame at a fixed spot on the 1920x1080 canvas.
export const AppWindow: React.FC<{
  x: number;
  y: number;
  w: number;
  h: number;
  title: string;
  icon?: React.ReactNode;
  style?: React.CSSProperties;
  children: React.ReactNode;
}> = ({ x, y, w, h, title, icon, style, children }) => (
  <div
    style={{
      position: "absolute",
      left: x,
      top: y,
      width: w,
      height: h,
      background: WIN.bg,
      borderRadius: 16,
      border: `1px solid ${WIN.line}`,
      boxShadow: "0 30px 80px rgba(0,0,0,0.55)",
      overflow: "hidden",
      color: WIN.text,
      ...style,
    }}
  >
    <div
      style={{
        height: TITLE_H,
        display: "flex",
        alignItems: "center",
        padding: "0 22px",
        gap: 14,
        fontSize: 22,
        color: WIN.muted,
        background: WIN.side,
      }}
    >
      {icon}
      <span style={{ flex: 1 }}>{title}</span>
      <span style={{ letterSpacing: 34, fontSize: 20 }}>─ ☐ ✕</span>
    </div>
    <div style={{ position: "absolute", top: TITLE_H, left: 0, right: 0, bottom: 0 }}>{children}</div>
  </div>
);
