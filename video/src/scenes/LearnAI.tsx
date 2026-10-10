import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { AppWindow, TITLE_H } from "../components/AppWindow";
import { Buddy } from "../components/Buddy";
import { Keycap } from "../components/Keycap";
import { Say, Scene } from "../components/Scene";
import { MicAsk, SceneTitle, TaskCard, typed, useEnter } from "../components/TuroPanel";
import { C } from "../theme";

// Window spot; the chat UI is laid out relative to its content area (below the title bar).
const WX = 70;
const WY = 90;
const SIDE_W = 300;
const BOX = { x: 370, y: 480, w: 860, h: 170 };
const CLIP = { x: BOX.x + 44, y: BOX.y + BOX.h - 40 };
const toScreen = (x: number, y: number) => ({ x: WX + x, y: WY + TITLE_H + y });

const PROMPT = "You are a tutor. Summarize my notes in 5 bullet points, with one example each.";

// Timeline (frames).
const T = {
  mic: 14, talkTo: 95, thinkTo: 125, card: 127, buddy: 135,
  arrive1: 172, click1: 240, file: 244, arrive2: 270, type: 274, hint: 342, hide: 372,
};

const Paperclip: React.FC = () => (
  <svg width={34} height={34} viewBox="0 0 24 24" fill="none" stroke="#d4d4d4" strokeWidth={2} strokeLinecap="round">
    <path d="M21 11.5l-8.6 8.6a5.5 5.5 0 0 1-7.8-7.8l8.6-8.6a3.7 3.7 0 0 1 5.2 5.2l-8.6 8.6a1.8 1.8 0 0 1-2.6-2.6l7.9-7.9" />
  </svg>
);

const ChatApp: React.FC = () => {
  const frame = useCurrentFrame();
  const text = typed(PROMPT, frame, T.type, 0.8);
  const fileIn = useEnter(T.file);
  const hintIn = useEnter(T.hint);
  const sendGlow = frame >= T.hint ? 0.5 + 0.5 * Math.sin((frame - T.hint) / 5) : 0;
  return (
    <AppWindow x={WX} y={WY} w={1300} h={900} title="AI Chat" style={useEnter(0)}>
      <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: SIDE_W, background: "#181818", padding: 22 }}>
        <div style={{ fontSize: 24, padding: "12px 16px", borderRadius: 10, background: "#262626" }}>✎ New chat</div>
        <div style={{ fontSize: 20, color: "#8a8a8a", margin: "30px 16px 12px" }}>Recent</div>
        {["Trip ideas for Baguio", "Email to my landlord", "Resume tips"].map((t) => (
          <div key={t} style={{ fontSize: 22, color: "#cfcfcf", padding: "10px 16px" }}>{t}</div>
        ))}
      </div>
      <div
        style={{
          position: "absolute", left: SIDE_W, right: 0, top: 300, textAlign: "center", fontSize: 50, fontWeight: 600,
          opacity: interpolate(frame, [T.file - 10, T.file], [1, 0.25], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }),
        }}
      >
        What can I help with?
      </div>
      {frame >= T.file ? (
        <div
          style={{
            ...fileIn, position: "absolute", left: BOX.x, top: BOX.y - 76, display: "flex", alignItems: "center", gap: 14,
            background: "#2a2a2a", border: "1px solid #3a3a3a", borderRadius: 12, padding: "10px 18px", fontSize: 22,
          }}
        >
          <div style={{ width: 34, height: 40, borderRadius: 6, background: "#2563eb" }} />
          notes.docx
        </div>
      ) : null}
      <div
        style={{
          position: "absolute", left: BOX.x, top: BOX.y, width: BOX.w, height: BOX.h, borderRadius: 28,
          background: "#2a2a2a", border: "1px solid #3a3a3a", padding: "22px 30px", fontSize: 26, lineHeight: 1.35,
        }}
      >
        <span style={{ color: text ? "#fff" : "#8a8a8a" }}>{text || "Ask anything"}</span>
        <div style={{ position: "absolute", left: CLIP.x - BOX.x - 17, top: CLIP.y - BOX.y - 17 }}>
          <Paperclip />
        </div>
        <div
          style={{
            position: "absolute", right: 22, bottom: 16, width: 50, height: 50, borderRadius: 99,
            background: frame >= T.hint ? "#fff" : "#555", color: "#000", display: "grid", placeItems: "center",
            fontSize: 28, fontWeight: 700, boxShadow: `0 0 ${30 * sendGlow}px rgba(255,255,255,${0.6 * sendGlow})`,
          }}
        >
          ↑
        </div>
      </div>
      {frame >= T.hint ? (
        <div style={{ ...hintIn, position: "absolute", left: BOX.x, top: BOX.y + BOX.h + 110, fontSize: 28, color: C.accentInk, display: "flex", alignItems: "center", gap: 12 }}>
          Turo never hits send. Press <Keycap size={24}>Enter</Keycap> when you're ready.
        </div>
      ) : null}
    </AppWindow>
  );
};

// Learn to use an AI chat app: attach a file, then write a good prompt.
export const LearnAI: React.FC = () => {
  const clip = toScreen(CLIP.x + 4, CLIP.y + 6);
  const box = toScreen(BOX.x + 330, BOX.y + BOX.h - 40); // empty strip under the typed text
  return (
    <Scene vo="ai">
      <ChatApp />
      <div style={{ position: "absolute", left: 1420, top: 96, width: 450 }}>
        <SceneTitle eyebrow="LEARN AI" title="Summarize notes with AI" />
        <div style={{ marginTop: 40 }}>
          <MicAsk at={T.mic} talkTo={T.talkTo} thinkTo={T.thinkTo} text="How do I get AI to summarize my notes?" />
        </div>
        <div style={{ marginTop: 10 }}>
          <TaskCard
            at={T.card}
            title="Summarize your notes"
            steps={[
              { text: "Attach your notes", doneAt: T.file },
              { text: "Write a clear prompt", doneAt: T.hint },
            ]}
          />
        </div>
      </div>
      <Buddy
        stops={[
          { at: T.buddy, x: 1460, y: 700 },
          { at: T.arrive1, ...clip, label: "Attach your notes" },
          { at: T.arrive2, ...box, label: "I typed a prompt for you" },
        ]}
        clicks={[T.click1]}
        hideAt={T.hide}
      />
      <Say line="ai_1" at={T.arrive1 + 2} />
      <Say line="ai_2" at={T.arrive2 + 4} />
    </Scene>
  );
};
