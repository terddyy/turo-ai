import React from "react";
import { Easing, interpolate, useCurrentFrame } from "remotion";
import { C } from "../theme";

// A place the buddy flies to. It arrives at frame `at` (the flight takes FLIGHT frames before that).
// The first stop is where it appears.
// `flip` puts the label pill on the left of the cursor (for targets near the right edge).
export type Stop = { at: number; x: number; y: number; label?: string; flip?: boolean };

const FLIGHT = 20;
const PULSE = 22;
const ease = Easing.inOut(Easing.cubic);
const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

const placeAt = (stops: Stop[], frame: number) => {
  let { x, y } = stops[0];
  let label: Stop | null = null;
  for (let i = 1; i < stops.length; i++) {
    const from = stops[i - 1];
    const to = stops[i];
    if (frame < to.at - FLIGHT) break;
    const t = ease(Math.min(1, (frame - (to.at - FLIGHT)) / FLIGHT));
    const cx = (from.x + to.x) / 2;
    const cy = Math.min(from.y, to.y) - 140; // fly in an arc, like the app's buddy
    x = (1 - t) ** 2 * from.x + 2 * (1 - t) * t * cx + t * t * to.x;
    y = (1 - t) ** 2 * from.y + 2 * (1 - t) * t * cy + t * t * to.y;
    label = t >= 1 && to.label ? to : null;
  }
  return { x, y, label };
};

// Turo's blue buddy cursor: flies between stops, shows a dark label pill, and acts out clicks.
export const Buddy: React.FC<{ stops: Stop[]; clicks?: number[]; hideAt?: number }> = ({
  stops,
  clicks = [],
  hideAt = Infinity,
}) => {
  const frame = useCurrentFrame();
  const appear = stops[0].at;
  if (frame < appear) return null;
  const { x, y, label } = placeAt(stops, frame);
  const opacity =
    interpolate(frame, [appear, appear + 8], [0, 1], clamp) *
    interpolate(frame, [hideAt, hideAt + 8], [1, 0], clamp);
  const sinceClick = Math.min(...clicks.map((c) => (frame >= c ? frame - c : Infinity)));
  const press = sinceClick < 8 ? interpolate(sinceClick, [0, 3, 8], [1, 0.82, 1]) : 1;
  const pillIn = label ? interpolate(frame, [label.at, label.at + 8], [0, 1], clamp) : 0;
  return (
    <div style={{ position: "absolute", left: x, top: y, opacity, pointerEvents: "none" }}>
      {sinceClick < PULSE ? (
        <div
          style={{
            position: "absolute",
            left: -40,
            top: -40,
            width: 80,
            height: 80,
            borderRadius: 999,
            border: `5px solid ${C.buddy}`,
            transform: `scale(${interpolate(sinceClick, [0, PULSE], [0.3, 1.8])})`,
            opacity: interpolate(sinceClick, [0, PULSE], [0.9, 0]),
          }}
        />
      ) : null}
      <svg
        width={58}
        height={72}
        viewBox="0 0 29 36"
        style={{
          position: "absolute",
          left: -3,
          top: -2,
          transform: `scale(${press})`,
          transformOrigin: "0 0",
          filter: `drop-shadow(0 0 14px ${C.buddy}) drop-shadow(0 4px 8px rgba(0,0,0,0.5))`,
        }}
      >
        <path
          d="M2 2 L2 29 L9 22.5 L14 33 L19 31 L14 20.5 L23.5 20.5 Z"
          fill={C.buddy}
          stroke="white"
          strokeWidth={2}
          strokeLinejoin="round"
        />
      </svg>
      {label ? (
        <div
          style={{
            position: "absolute",
            ...(label.flip ? { right: 16 } : { left: 54 }),
            top: 56,
            opacity: pillIn,
            transform: `translateY(${(1 - pillIn) * 10}px)`,
            background: C.ink,
            border: "1px solid rgba(255,255,255,0.14)",
            borderRadius: 999,
            padding: "14px 26px",
            fontSize: 32,
            fontWeight: 600,
            whiteSpace: "nowrap",
            boxShadow: "0 10px 30px rgba(0,0,0,0.45)",
          }}
        >
          {label.label}
        </div>
      ) : null}
    </div>
  );
};
