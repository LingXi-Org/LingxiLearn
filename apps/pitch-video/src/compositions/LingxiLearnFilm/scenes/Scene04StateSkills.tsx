import {AbsoluteFill, interpolate, useCurrentFrame} from "remotion";
import {GoalCard, SkillCard} from "../components/Cards";
import {COPY} from "../copy";
import {SKILLS, STATES} from "../constants";
import {FILM_THEME as T} from "../theme";
import {clamp, enter, progress} from "../utils/animation";

const statePositions = [[285, 190], [1260, 190], [270, 690], [1275, 690]] as const;

export const Scene04StateSkills: React.FC = () => {
  const frame = useCurrentFrame();
  const gather = progress(frame, 65, 136);
  const selected = progress(frame, 138, 210);
  const morph = progress(frame, 248, 329);
  return (
    <AbsoluteFill style={{background: T.paper, overflow: "hidden"}}>
      <div style={{position: "absolute", left: "50%", top: interpolate(gather, [0, 1], [412, 214], clamp), transform: `translateX(-50%) scale(${interpolate(morph, [0, 1], [1, .86], clamp)})`, opacity: 1 - morph}}><GoalCard compact /></div>
      <svg width="1920" height="1080" style={{position: "absolute", inset: 0, opacity: (1 - morph) * enter(frame, 15, 28)}}>
        {statePositions.map(([x, y], i) => <line key={i} x1={x + 170} y1={y + 35} x2="960" y2="470" stroke={T.line} strokeWidth="2" strokeDasharray="7 10" />)}
      </svg>
      {STATES.map((label, i) => <div key={label} style={{position: "absolute", left: interpolate(gather, [0, 1], [statePositions[i][0], 535 + i * 215], clamp), top: interpolate(gather, [0, 1], [statePositions[i][1], 356], clamp), padding: "15px 19px", borderRadius: 14, background: T.white, border: `1px solid ${T.line}`, fontSize: 18, opacity: enter(frame, 18 + i * 7, 22) * (1 - progress(frame, 122, 148))}}>{label}</div>)}
      <div style={{position: "absolute", left: "50%", top: 510, transform: "translateX(-50%)", display: "flex", gap: 17, opacity: progress(frame, 82, 122) * (1 - morph)}}>
        {SKILLS.map((skill) => <div key={skill} style={{opacity: skill === "Visualize" ? 1 : interpolate(selected, [0, 1], [1, .25], clamp), transform: skill === "Visualize" ? `scale(${interpolate(selected, [0, 1], [1, 1.08], clamp)})` : undefined}}><SkillCard label={skill} selected={skill === "Visualize" && selected > .35} /></div>)}
      </div>
      <div style={{position: "absolute", left: "50%", top: 705, transform: "translateX(-50%)", fontSize: 42, fontWeight: 500, opacity: progress(frame, 202, 224) * (1 - progress(frame, 242, 257))}}>{COPY.stateDecides}</div>
      <div style={{position: "absolute", left: interpolate(morph, [0, 1], [970, 135], clamp), top: interpolate(morph, [0, 1], [510, 118], clamp), width: interpolate(morph, [0, 1], [220, 1650], clamp), height: interpolate(morph, [0, 1], [98, 844], clamp), borderRadius: interpolate(morph, [0, 1], [20, 28], clamp), background: T.ink, color: T.white, display: "flex", alignItems: "center", justifyContent: "center", fontSize: interpolate(morph, [0, 1], [23, 54], clamp), fontWeight: 500, opacity: morph}}>Visualize</div>
    </AbsoluteFill>
  );
};
