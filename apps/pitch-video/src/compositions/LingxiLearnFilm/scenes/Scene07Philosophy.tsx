import {AbsoluteFill, interpolate, useCurrentFrame} from "remotion";
import {SkillCard} from "../components/Cards";
import {COPY} from "../copy";
import {SKILLS} from "../constants";
import {FILM_THEME as T} from "../theme";
import {clamp, progress} from "../utils/animation";

export const Scene07Philosophy: React.FC = () => {
  const frame = useCurrentFrame();
  const gridOut = progress(frame, 42, 72);
  const first = progress(frame, 42, 72);
  const second = progress(frame, 96, 128);
  return (
    <AbsoluteFill style={{background: T.ink, color: T.white, alignItems: "center", justifyContent: "center", overflow: "hidden"}}>
      <div style={{position: "absolute", top: 454, display: "flex", gap: 16, opacity: 1 - gridOut, transform: `scale(${interpolate(gridOut, [0, 1], [1, .82], clamp)})`}}>{SKILLS.map((skill) => <div key={skill} style={{filter: "invert(1)"}}><SkillCard label={skill} /></div>)}</div>
      <div style={{fontSize: 82, fontWeight: 500, letterSpacing: "-.055em", transform: `translateY(${interpolate(second, [0, 1], [30, -38], clamp)})`, opacity: first}}>{COPY.philosophy1}</div>
      <div style={{fontSize: 82, fontWeight: 500, letterSpacing: "-.055em", color: T.accent, marginTop: 34, opacity: second, transform: `translateY(${interpolate(second, [0, 1], [24, 20], clamp)})`}}>{COPY.philosophy2}</div>
    </AbsoluteFill>
  );
};
