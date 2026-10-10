import vo from "./vo.json";

export const FPS = 30;
export const VO_DELAY = 6; // frames of quiet before each scene's narration

// A scene lasts as long as its narration (+ padding), but never shorter than this.
const MIN_SECONDS = {
  hook: 5,
  intro: 5.5,
  device: 13,
  ai: 13,
  local: 7,
  outro: 5,
} as const;

export type SceneId = keyof typeof MIN_SECONDS;
export const SCENES: SceneId[] = ["hook", "intro", "device", "ai", "local", "outro"];

export const sceneFrames = (id: SceneId): number =>
  Math.ceil(Math.max(vo[id] + 0.8, MIN_SECONDS[id]) * FPS);

export const TOTAL_FRAMES = SCENES.reduce((sum, id) => sum + sceneFrames(id), 0);

// Length of a voice line in frames (for Turo's in-scene step lines).
export const voFrames = (id: keyof typeof vo): number => Math.ceil(vo[id] * FPS);
