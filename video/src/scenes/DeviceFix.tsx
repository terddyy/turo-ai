import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { AppWindow, TITLE_H } from "../components/AppWindow";
import { Buddy } from "../components/Buddy";
import { Say, Scene } from "../components/Scene";
import { AskBar, SceneTitle, TaskCard, useEnter } from "../components/TuroPanel";
import { C, WIN } from "../theme";

// Window spot; everything inside is laid out relative to its content area (below the title bar).
const WX = 70;
const WY = 90;
const SIDE_W = 380;
const LIST_Y = 200; // first sidebar row
const ROW_H = 54;
const MAIN_X = SIDE_W + 44;
const MAIN_W = 1300 - SIDE_W - 88;
const ADD_BTN = { x: MAIN_X + MAIN_W - 230, y: 254, w: 230, h: 54 };
const toScreen = (x: number, y: number) => ({ x: WX + x, y: WY + TITLE_H + y });

// Timeline (frames).
const T = {
  ask: 14, type: 24, thinkTo: 120, card: 122, buddy: 130,
  arrive1: 196, click1: 252, page: 256, arrive2: 290, click2: 336, connected: 344, hide: 372,
};

const CATEGORIES: [string, string][] = [
  ["System", "#4cc2ff"], ["Bluetooth & devices", "#3b82f6"], ["Network & internet", "#60a5fa"],
  ["Personalization", "#f59e0b"], ["Apps", "#a78bfa"], ["Accounts", "#34d399"],
  ["Time & language", "#38bdf8"], ["Gaming", "#9ca3af"], ["Accessibility", "#60a5fa"],
  ["Privacy & security", "#9ca3af"], ["Windows Update", "#4cc2ff"],
];

const Tile: React.FC<{ title: string; sub: string; y: number; right?: React.ReactNode; style?: React.CSSProperties }> = ({
  title, sub, y, right, style,
}) => (
  <div
    style={{
      position: "absolute", left: MAIN_X, top: y, width: MAIN_W, height: 88, borderRadius: 10,
      background: WIN.card, display: "flex", alignItems: "center", padding: "0 26px", gap: 20, ...style,
    }}
  >
    <div style={{ width: 40, height: 40, borderRadius: 10, background: "#3a3a3a" }} />
    <div style={{ flex: 1 }}>
      <div style={{ fontSize: 26 }}>{title}</div>
      <div style={{ fontSize: 20, color: WIN.muted }}>{sub}</div>
    </div>
    {right}
  </div>
);

const Toggle: React.FC = () => (
  <div style={{ display: "flex", alignItems: "center", gap: 14, fontSize: 22 }}>
    On
    <div style={{ width: 56, height: 28, borderRadius: 99, background: WIN.accent, position: "relative" }}>
      <div style={{ position: "absolute", right: 5, top: 5, width: 18, height: 18, borderRadius: 99, background: "#000" }} />
    </div>
  </div>
);

const SettingsApp: React.FC = () => {
  const frame = useCurrentFrame();
  const onBt = frame >= T.page;
  const fade = interpolate(frame, [T.page, T.page + 8], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const pressed = frame >= T.click2 && frame < T.click2 + 8;
  const connectedIn = useEnter(T.connected);
  return (
    <AppWindow x={WX} y={WY} w={1300} h={900} title="Settings" style={useEnter(0)}>
      <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: SIDE_W, background: WIN.side }}>
        <div style={{ display: "flex", alignItems: "center", gap: 18, padding: "26px 26px" }}>
          <div style={{ width: 64, height: 64, borderRadius: 99, background: "#4b5563" }} />
          <div>
            <div style={{ fontSize: 24 }}>Local account</div>
            <div style={{ fontSize: 18, color: WIN.muted }}>This laptop</div>
          </div>
        </div>
        <div style={{ margin: "0 24px", height: 52, borderRadius: 8, background: WIN.card, color: WIN.muted, fontSize: 22, padding: "12px 18px" }}>
          Find a setting
        </div>
        {CATEGORIES.map(([name, color], i) => {
          const selected = i === (onBt ? 1 : 0);
          return (
            <div
              key={name}
              style={{
                position: "absolute", left: 14, right: 14, top: LIST_Y + i * ROW_H, height: ROW_H - 6,
                borderRadius: 8, background: selected ? "#2d2d2d" : "transparent",
                display: "flex", alignItems: "center", gap: 18, padding: "0 16px", fontSize: 24,
              }}
            >
              <div style={{ width: 4, height: 24, borderRadius: 4, background: selected ? WIN.accent : "transparent" }} />
              <div style={{ width: 26, height: 26, borderRadius: 7, background: color }} />
              {name}
            </div>
          );
        })}
      </div>
      {!onBt ? (
        <>
          <div style={{ position: "absolute", left: MAIN_X, top: 30, fontSize: 46, fontWeight: 600 }}>System</div>
          {[["Display", "Monitors, brightness, night light"], ["Sound", "Volume levels, output, input"],
            ["Notifications", "Alerts from apps and system"], ["Power & battery", "Sleep, battery usage"],
            ["Storage", "Storage space, drives"]].map(([t, s], i) => (
            <Tile key={t} title={t} sub={s} y={120 + i * 100} />
          ))}
        </>
      ) : (
        <div style={{ opacity: fade }}>
          <div style={{ position: "absolute", left: MAIN_X, top: 30, fontSize: 46, fontWeight: 600 }}>Bluetooth &amp; devices</div>
          <Tile title="Bluetooth" sub='Discoverable as "TURO-LAPTOP"' y={120} right={<Toggle />} />
          <div style={{ position: "absolute", left: MAIN_X, top: ADD_BTN.y + 12, fontSize: 28, fontWeight: 600 }}>Devices</div>
          <div
            style={{
              position: "absolute", left: ADD_BTN.x, top: ADD_BTN.y, width: ADD_BTN.w, height: ADD_BTN.h,
              borderRadius: 8, background: pressed ? "#3a3a3a" : WIN.cardHi, border: `1px solid ${WIN.line}`,
              display: "grid", placeItems: "center", fontSize: 24,
            }}
          >
            + Add device
          </div>
          <Tile title="Mouse" sub="Connected" y={330} />
          <Tile title="Keyboard" sub="Paired" y={430} />
          {frame >= T.connected ? (
            <Tile
              title="Headphones"
              sub="Connected · Voice, music"
              y={530}
              style={{
                border: `2px solid ${C.ok}`,
                boxShadow: `0 0 40px rgba(52,211,153,${interpolate(frame, [T.connected, T.connected + 30], [0.6, 0.15], { extrapolateRight: "clamp" })})`,
                ...connectedIn,
              }}
              right={<span style={{ color: C.ok, fontSize: 24, fontWeight: 600 }}>✓ Connected</span>}
            />
          ) : null}
        </div>
      )}
    </AppWindow>
  );
};

// Troubleshoot a device in Windows Settings: ask, then Turo points the way step by step.
export const DeviceFix: React.FC = () => {
  const bt = toScreen(335, LIST_Y + ROW_H + 8); // just past the label, so it stays readable
  const add = toScreen(ADD_BTN.x + 205, ADD_BTN.y + 34);
  return (
    <Scene vo="device">
      <SettingsApp />
      <div style={{ position: "absolute", left: 1420, top: 96, width: 450 }}>
        <SceneTitle eyebrow="FIX A DEVICE" title="Headphones won't connect" />
        <div style={{ marginTop: 40 }}>
          <AskBar at={T.ask} typeFrom={T.type} thinkTo={T.thinkTo} text="My Bluetooth headphones won't connect" />
        </div>
        <div style={{ marginTop: 10 }}>
          <TaskCard
            at={T.card}
            title="Connect your headphones"
            steps={[
              { text: "Open Bluetooth & devices", doneAt: T.page },
              { text: "Click Add device", doneAt: T.connected },
            ]}
          />
        </div>
      </div>
      <Buddy
        stops={[
          { at: T.buddy, x: 1460, y: 700 },
          { at: T.arrive1, ...bt, label: "Click Bluetooth & devices" },
          { at: T.arrive2, ...add, label: "Click Add device", flip: true },
        ]}
        clicks={[T.click1, T.click2]}
        hideAt={T.hide}
      />
      <Say line="device_1" at={T.arrive1 + 2} />
      <Say line="device_2" at={T.arrive2 + 2} />
    </Scene>
  );
};
