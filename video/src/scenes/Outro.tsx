import React from "react";
import { Img, spring, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { Keycap } from "../components/Keycap";
import { Scene } from "../components/Scene";
import { useEnter } from "../components/TuroPanel";
import { C } from "../theme";

// End card: logo, name, meaning, and the two ways to ask.
export const Outro: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const pop = spring({ frame, fps, config: { damping: 12 } });
  return (
    <Scene vo="outro">
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
        <div style={{ display: "flex", alignItems: "center", gap: 40 }}>
          <Img
            src={staticFile("turo-logo.png")}
            style={{ width: 200, height: 200, transform: `scale(${pop})`, filter: "drop-shadow(0 0 50px rgba(79,143,248,0.5))" }}
          />
          <div style={{ fontSize: 170, fontWeight: 800, letterSpacing: -4, ...useEnter(6) }}>
            Turo <span style={{ color: C.accent }}>ai</span>
          </div>
        </div>
        <div style={{ fontSize: 52, color: C.soft, marginTop: 30, ...useEnter(16) }}>
          <i>Turo</i> (Tagalog): to point, to teach.
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 18, fontSize: 40, color: C.muted, marginTop: 70, ...useEnter(28) }}>
          <Keycap size={36}>F9</Keycap> type
          <span style={{ width: 50 }} />
          <Keycap size={36}>Win</Keycap>+<Keycap size={36}>Alt</Keycap> talk
        </div>
      </div>
    </Scene>
  );
};
