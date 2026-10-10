import React from "react";
import { Img, spring, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { Scene } from "../components/Scene";
import { useEnter } from "../components/TuroPanel";
import { C } from "../theme";

// Logo reveal: "Turo ai".
export const Intro: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const pop = spring({ frame, fps, config: { damping: 11, mass: 0.8 } });
  const glow = 0.45 + 0.15 * Math.sin(frame / 10);
  return (
    <Scene vo="intro">
      <div
        style={{
          position: "absolute",
          inset: 0,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <Img
          src={staticFile("turo-logo.png")}
          style={{
            width: 280,
            height: 280,
            transform: `scale(${pop}) rotate(${(1 - pop) * -20}deg)`,
            filter: `drop-shadow(0 0 60px rgba(79,143,248,${glow}))`,
          }}
        />
        <div style={{ fontSize: 180, fontWeight: 800, letterSpacing: -4, marginTop: 20, ...useEnter(12) }}>
          Turo <span style={{ color: C.accent }}>ai</span>
        </div>
        <div style={{ fontSize: 56, color: C.soft, marginTop: 6, ...useEnter(30) }}>
          Points at what to click. Right on your screen.
        </div>
      </div>
    </Scene>
  );
};
