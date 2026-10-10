import React from "react";
import {
  AbsoluteFill,
  Html5Audio,
  interpolate,
  Sequence,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { BG, C, FONT } from "../theme";
import { VO_DELAY } from "../timing";

// Scene shell: Turo's navy background, fade in/out, and the scene's narration line.
export const Scene: React.FC<{ vo?: string; children: React.ReactNode }> = ({ vo, children }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const opacity = interpolate(frame, [0, 8, durationInFrames - 8, durationInFrames], [0, 1, 1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  return (
    <AbsoluteFill style={{ background: BG, fontFamily: FONT, color: C.text }}>
      <AbsoluteFill style={{ opacity }}>{children}</AbsoluteFill>
      {vo ? (
        <Sequence from={VO_DELAY} name={`VO ${vo}`}>
          <Html5Audio src={staticFile(`vo/${vo}.wav`)} />
        </Sequence>
      ) : null}
    </AbsoluteFill>
  );
};

// One of Turo's own spoken lines, starting at `at`.
export const Say: React.FC<{ line: string; at: number }> = ({ line, at }) => (
  <Sequence from={at} name={`Turo says ${line}`}>
    <Html5Audio src={staticFile(`vo/${line}.wav`)} />
  </Sequence>
);
