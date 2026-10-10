import React from "react";
import { Composition, Folder } from "remotion";
import { SCENE_COMPONENTS, TuroLaunch } from "./TuroLaunch";
import { FPS, SCENES, sceneFrames, TOTAL_FRAMES } from "./timing";

export const RemotionRoot: React.FC = () => (
  <>
    <Composition id="TuroLaunch" component={TuroLaunch} durationInFrames={TOTAL_FRAMES} fps={FPS} width={1920} height={1080} />
    <Folder name="Scenes">
      {SCENES.map((id) => (
        <Composition
          key={id}
          id={`Scene-${id}`}
          component={SCENE_COMPONENTS[id]}
          durationInFrames={sceneFrames(id)}
          fps={FPS}
          width={1920}
          height={1080}
        />
      ))}
    </Folder>
  </>
);
