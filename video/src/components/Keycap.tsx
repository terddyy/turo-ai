import React from "react";
import { C, MONO } from "../theme";

// Keyboard key, styled like QLabel#key in turo/ui/style.py.
export const Keycap: React.FC<{ children: React.ReactNode; size?: number }> = ({ children, size = 30 }) => (
  <span
    style={{
      display: "inline-block",
      background: C.surfaceHi,
      color: C.text,
      border: `2px solid ${C.lineHi}`,
      borderBottom: "6px solid #0b1324",
      borderRadius: size * 0.35,
      padding: `${size * 0.15}px ${size * 0.45}px`,
      fontFamily: MONO,
      fontSize: size,
      fontWeight: 600,
      lineHeight: 1.2,
    }}
  >
    {children}
  </span>
);
