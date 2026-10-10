import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { Scene } from "../components/Scene";
import { useEnter } from "../components/TuroPanel";
import { C, WIN } from "../theme";

const Bar: React.FC<{ w: number | string; c: string; h?: number }> = ({ w, c, h = 22 }) => (
  <div style={{ width: w, height: h, borderRadius: 6, background: c, marginBottom: 16 }} />
);

const Card: React.FC<{ x: number; tilt: number; at: number; label: string; children: React.ReactNode }> = ({
  x,
  tilt,
  at,
  label,
  children,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame: frame - at, fps, config: { damping: 16 } });
  return (
    <div
      style={{
        position: "absolute",
        left: x,
        top: 330,
        width: 680,
        opacity: frame < at ? 0 : s,
        transform: `translateY(${(1 - s) * 60}px) rotate(${tilt}deg)`,
      }}
    >
      <div style={{ fontSize: 40, fontWeight: 700, color: C.soft, marginBottom: 18 }}>{label}</div>
      <div
        style={{
          height: 420,
          borderRadius: 20,
          overflow: "hidden",
          position: "relative",
          boxShadow: "0 30px 70px rgba(0,0,0,0.5)",
        }}
      >
        {children}
      </div>
    </div>
  );
};

// "Stuck?" The tutorial screenshot never matches your own screen.
export const Hook: React.FC = () => {
  const frame = useCurrentFrame();
  const shake = frame > 60 && frame < 75 ? Math.sin(frame * 2.2) * 8 : 0;
  const neq = interpolate(frame, [55, 65], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <Scene vo="hook">
      <div
        style={{
          position: "absolute",
          top: 110,
          width: "100%",
          textAlign: "center",
          fontSize: 120,
          fontWeight: 800,
          ...useEnter(4),
        }}
      >
        Stuck on your computer?
      </div>
      <Card x={180} tilt={-3} at={18} label="The tutorial">
        <div style={{ position: "absolute", inset: 0, background: "#e9e9e9", padding: 34 }}>
          <Bar w="60%" c="#b9b9b9" h={30} />
          <Bar w="85%" c="#cfcfcf" />
          <Bar w="70%" c="#cfcfcf" />
          <div style={{ display: "flex", gap: 20, marginTop: 30 }}>
            {[0, 1, 2].map((i) => (
              <div key={i} style={{ width: 170, height: 120, borderRadius: 10, background: "#d6d6d6" }} />
            ))}
          </div>
          <div
            style={{
              position: "absolute",
              left: 400,
              top: 200,
              width: 230,
              height: 170,
              borderRadius: 999,
              border: "8px solid #ef4444",
            }}
          />
        </div>
      </Card>
      <div
        style={{
          position: "absolute",
          left: 900,
          top: 520,
          width: 120,
          textAlign: "center",
          fontSize: 130,
          fontWeight: 800,
          color: C.warn,
          opacity: neq,
          transform: `scale(${0.5 + neq * 0.5})`,
        }}
      >
        ≠
      </div>
      <Card x={1060} tilt={2} at={30} label="Your screen">
        <div
          style={{
            position: "absolute",
            inset: 0,
            background: WIN.bg,
            display: "flex",
            transform: `translateX(${shake}px)`,
          }}
        >
          <div style={{ width: 190, background: WIN.side, padding: 24 }}>
            {[0, 1, 2, 3, 4, 5].map((i) => (
              <Bar key={i} w="100%" c={i === 1 ? "#3d5a80" : "#333"} />
            ))}
          </div>
          <div style={{ flex: 1, padding: 30 }}>
            <Bar w="55%" c="#4a4a4a" h={30} />
            {[0, 1, 2].map((i) => (
              <div key={i} style={{ height: 70, borderRadius: 10, background: WIN.card, marginBottom: 14 }} />
            ))}
          </div>
          <div
            style={{
              position: "absolute",
              left: 380,
              top: 140,
              fontSize: 110,
              fontWeight: 800,
              color: C.muted,
              opacity: interpolate(frame, [70, 80], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }),
            }}
          >
            ?
          </div>
        </div>
      </Card>
    </Scene>
  );
};
