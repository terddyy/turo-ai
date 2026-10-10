import React from "react";
import { Img, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { C } from "../theme";
import { Keycap } from "./Keycap";

const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

// Pop-in used by the panel pieces: fade + slide up from frame `at`.
export const useEnter = (at: number): React.CSSProperties => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame: frame - at, fps, config: { damping: 18 } });
  return { opacity: frame < at ? 0 : s, transform: `translateY(${(1 - s) * 30}px)` };
};

// Text revealed one character every `perChar` frames from frame `from`.
export const typed = (text: string, frame: number, from: number, perChar = 0.9): string =>
  text.slice(0, Math.max(0, Math.floor((frame - from) / perChar)));

const Caret: React.FC = () => {
  const frame = useCurrentFrame();
  return <span style={{ opacity: Math.floor(frame / 15) % 2 ? 0 : 1, color: C.accent }}>|</span>;
};

export const SceneTitle: React.FC<{ eyebrow: string; title: string }> = ({ eyebrow, title }) => (
  <div style={useEnter(4)}>
    <div style={{ color: C.accent, fontSize: 26, fontWeight: 700, letterSpacing: 4 }}>{eyebrow}</div>
    <div style={{ fontSize: 64, fontWeight: 800, lineHeight: 1.05, marginTop: 10 }}>{title}</div>
  </div>
);

const box: React.CSSProperties = {
  background: "#080d18",
  border: `2px solid ${C.accent}`,
  borderRadius: 18,
  padding: "18px 22px",
  fontSize: 32,
  lineHeight: 1.3,
  minHeight: 128,
};

// Turo's F9 ask box: the question types itself in, then "Thinking" dots.
export const AskBar: React.FC<{ at: number; text: string; typeFrom: number; thinkTo: number }> = ({
  at,
  text,
  typeFrom,
  thinkTo,
}) => {
  const frame = useCurrentFrame();
  const shown = typed(text, frame, typeFrom);
  const thinking = shown.length === text.length && frame < thinkTo;
  return (
    <div style={useEnter(at)}>
      <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 14, fontSize: 28 }}>
        <Keycap size={26}>F9</Keycap>
        <span style={{ color: C.muted }}>Ask Turo</span>
      </div>
      <div style={box}>
        {shown}
        {shown.length < text.length ? <Caret /> : null}
      </div>
      <Status show={thinking} />
    </div>
  );
};

const Status: React.FC<{ show: boolean }> = ({ show }) => {
  const frame = useCurrentFrame();
  const dots = ".".repeat(1 + (Math.floor(frame / 8) % 3));
  return (
    <div style={{ height: 44, marginTop: 12, fontSize: 28, color: C.accentInk, opacity: show ? 1 : 0 }}>
      Reading your screen{dots}
    </div>
  );
};

// Hold Win+Alt to talk: live mic bars and the transcript appearing word by word.
export const MicAsk: React.FC<{ at: number; text: string; talkTo: number; thinkTo: number }> = ({
  at,
  text,
  talkTo,
  thinkTo,
}) => {
  const frame = useCurrentFrame();
  const words = text.split(" ");
  const n = Math.round(interpolate(frame, [at + 10, talkTo], [0, words.length], clamp));
  const talking = frame < talkTo;
  return (
    <div style={useEnter(at)}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 14, fontSize: 28 }}>
        <Keycap size={26}>Win</Keycap>+<Keycap size={26}>Alt</Keycap>
        <span style={{ color: C.muted, marginLeft: 6 }}>Talk to Turo</span>
      </div>
      <div style={box}>
        <div style={{ display: "flex", gap: 8, alignItems: "center", height: 48, marginBottom: 6 }}>
          {Array.from({ length: 9 }, (_, i) => {
            const level = talking ? 0.35 + 0.65 * Math.abs(Math.sin(frame * 0.35 + i * 1.3)) : 0.12;
            return (
              <div
                key={i}
                style={{ width: 9, height: 48 * level, borderRadius: 9, background: C.accent }}
              />
            );
          })}
        </div>
        <span style={{ fontStyle: "italic" }}>“{words.slice(0, n).join(" ")}”</span>
      </div>
      <Status show={!talking && frame < thinkTo} />
    </div>
  );
};

export type Step = { text: string; doneAt: number };

// The task card (turo/ui/card.py): task title, checklist of steps, Next / Do it / Stop.
export const TaskCard: React.FC<{ at: number; title: string; steps: Step[] }> = ({ at, title, steps }) => {
  const frame = useCurrentFrame();
  const done = steps.filter((s) => frame >= s.doneAt).length;
  const finished = done === steps.length;
  return (
    <div
      style={{
        ...useEnter(at),
        background: "#0d1526",
        border: `2px solid ${C.lineHi}`,
        borderTop: `4px solid ${C.accent}`,
        borderRadius: 22,
        padding: "22px 26px",
        boxShadow: "0 20px 50px rgba(0,0,0,0.45)",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 12, fontSize: 26, color: "#93c5fd", fontWeight: 600 }}>
        <Img src={staticFile("turo-logo.png")} style={{ width: 36, height: 36 }} />
        {finished ? "Turo · done" : `Turo · step ${done + 1} of ${steps.length}`}
      </div>
      <div style={{ fontSize: 32, fontWeight: 700, margin: "14px 0 16px" }}>{title}</div>
      {steps.map((s, i) => {
        const isDone = frame >= s.doneAt;
        const active = i === done;
        return (
          <div
            key={s.text}
            style={{ display: "flex", alignItems: "center", gap: 14, fontSize: 28, margin: "10px 0" }}
          >
            <div
              style={{
                width: 38,
                height: 38,
                borderRadius: 99,
                display: "grid",
                placeItems: "center",
                fontSize: 22,
                fontWeight: 700,
                background: isDone ? C.ok : active ? C.accent : "transparent",
                border: isDone || active ? "none" : `2px solid ${C.lineHi}`,
                color: isDone ? "#04241a" : "white",
              }}
            >
              {isDone ? "✓" : i + 1}
            </div>
            <span style={{ color: isDone ? C.muted : C.text, textDecoration: isDone ? "line-through" : "none" }}>
              {s.text}
            </span>
          </div>
        );
      })}
      <div style={{ display: "flex", gap: 10, marginTop: 18, fontSize: 24 }}>
        {["Next", "Do it", "Stop"].map((b, i) => (
          <div
            key={b}
            style={{
              padding: "8px 20px",
              borderRadius: 12,
              background: i === 0 ? `linear-gradient(#5b97fa, ${C.accentDeep})` : C.surfaceHi,
              border: `1px solid ${i === 0 ? "#6aa4ff" : "#22314f"}`,
              fontWeight: i === 0 ? 600 : 400,
            }}
          >
            {b}
          </div>
        ))}
      </div>
    </div>
  );
};
