import {AbsoluteFill, interpolate, useCurrentFrame} from "remotion";
import {GoalCard, SkillCard} from "../../LingxiLearnFilm/components/Cards";
import {COPY} from "../../LingxiLearnFilm/copy";
import {SKILLS, STATES} from "../../LingxiLearnFilm/constants";
import {FILM_THEME as T} from "../../LingxiLearnFilm/theme";
import {clamp, enter, progress} from "../../LingxiLearnFilm/utils/animation";
import {StateCore3D} from "../components/StateCore3D";

const statePositions = [[250, 174], [1290, 174], [245, 710], [1295, 710]] as const;

export const Scene04StateSkills3D: React.FC = () => {
  const frame = useCurrentFrame();
  const gather = progress(frame, 65, 136);
  const selected = progress(frame, 138, 210);
  const morph = progress(frame, 248, 329);
  return (
    <AbsoluteFill style={{background: T.paper, overflow: "hidden"}}>
      <div style={{position: "absolute", inset: 0, opacity: enter(frame, 12, 28) * (1 - progress(frame, 228, 270))}}><StateCore3D /></div>
      <div style={{position: "absolute", left: "50%", top: interpolate(gather, [0, 1], [405, 112], clamp), transform: `translateX(-50%) scale(${interpolate(morph, [0, 1], [1, .86], clamp)})`, opacity: 1 - morph}}><GoalCard compact /></div>
      <svg width="1920" height="1080" style={{position: "absolute", inset: 0, opacity: (1 - morph) * enter(frame, 15, 28)}}>{statePositions.map(([x, y], index) => <line key={index} x1={x + 165} y1={y + 33} x2="960" y2="492" stroke={T.line} strokeWidth="2" strokeDasharray="7 10" />)}</svg>
      {STATES.map((label, index) => <div key={label} style={{position: "absolute", left: interpolate(gather, [0, 1], [statePositions[index][0], 535 + index * 215], clamp), top: interpolate(gather, [0, 1], [statePositions[index][1], 302], clamp), padding: "15px 19px", borderRadius: 14, background: "rgba(255,255,255,.92)", border: `1px solid ${T.line}`, fontSize: 18, opacity: enter(frame, 18 + index * 7, 22) * (1 - progress(frame, 122, 148)), boxShadow: "0 12px 30px rgba(0,0,0,.06)"}}>{label}</div>)}
      <div style={{position: "absolute", left: "50%", top: 590, transform: "translateX(-50%)", display: "flex", gap: 17, opacity: progress(frame, 82, 122) * (1 - morph)}}>{SKILLS.map((skill) => <div key={skill} style={{opacity: skill === "Visualize" ? 1 : interpolate(selected, [0, 1], [1, .22], clamp), transform: skill === "Visualize" ? `scale(${interpolate(selected, [0, 1], [1, 1.08], clamp)})` : undefined}}><SkillCard label={skill} selected={skill === "Visualize" && selected > .35} /></div>)}</div>
      <div style={{position: "absolute", left: "50%", top: 760, transform: "translateX(-50%)", fontSize: 42, fontWeight: 500, opacity: progress(frame, 202, 224) * (1 - progress(frame, 242, 257))}}>{COPY.stateDecides}</div>
      <div style={{position: "absolute", left: interpolate(morph, [0, 1], [970, 52], clamp), top: interpolate(morph, [0, 1], [590, 52], clamp), width: interpolate(morph, [0, 1], [220, 1816], clamp), height: interpolate(morph, [0, 1], [98, 976], clamp), borderRadius: interpolate(morph, [0, 1], [20, 32], clamp), background: T.ink, color: T.white, display: "flex", alignItems: "center", justifyContent: "center", fontSize: interpolate(morph, [0, 1], [23, 54], clamp), fontWeight: 500, opacity: morph}}>Visualize</div>
    </AbsoluteFill>
  );
};
