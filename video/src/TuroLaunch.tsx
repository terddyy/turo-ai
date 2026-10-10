import React from "react";
import { Series } from "remotion";
import { DeviceFix } from "./scenes/DeviceFix";
import { Hook } from "./scenes/Hook";
import { Intro } from "./scenes/Intro";
import { LearnAI } from "./scenes/LearnAI";
import { Local } from "./scenes/Local";
import { Outro } from "./scenes/Outro";
import { SceneId, SCENES, sceneFrames } from "./timing";

export const SCENE_COMPONENTS: Record<SceneId, React.FC> = {
  hook: Hook,
  intro: Intro,
  device: DeviceFix,
  ai: LearnAI,
  local: Local,
  outro: Outro,
};

// The whole "Turo ai" launch video: six scenes back to back, each timed from its voiceover.
export const TuroLaunch: React.FC = () => (
  <Series>
    {SCENES.map((id) => {
      const SceneComponent = SCENE_COMPONENTS[id];
      return (
        <Series.Sequence key={id} name={id} durationInFrames={sceneFrames(id)}>
          <SceneComponent />
        </Series.Sequence>
      );
    })}
  </Series>
);
