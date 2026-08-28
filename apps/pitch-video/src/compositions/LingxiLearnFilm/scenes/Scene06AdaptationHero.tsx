import {AbsoluteFill, interpolate, useCurrentFrame} from "remotion";
import {EvidenceToken, ProductCard, SkillCard} from "../components/Cards";
import {LearningState} from "../components/LearningState";
import {PcaVisualization} from "../components/PcaVisualization";
import {COPY} from "../copy";
import {SKILLS} from "../constants";
import {FILM_THEME as T} from "../theme";
import {clamp, progress} from "../utils/animation";

export const Scene06AdaptationHero: React.FC = () => {
  const frame = useCurrentFrame();
  const absorb = progress(frame, 28, 76);
  const update = progress(frame, 74, 112);
  const stages = progress(frame, 100, 150) * (1 - progress(frame, 176, 205));
  const replace = progress(frame, 154, 215);
  const replan = progress(frame, 205, 242) * (1 - progress(frame, 282, 310));
  const result = progress(frame, 232, 286) * (1 - progress(frame, 302, 329));
  const grid = progress(frame, 306, 329);
  return (
    <AbsoluteFill style={{background: T.paper, overflow: "hidden"}}>
      <div style={{position: "absolute", left: interpolate(absorb, [0, 1], [842, 560], clamp), top: interpolate(absorb, [0, 1], [486, 495], clamp), opacity: 1 - progress(frame, 72, 94), transform: `scale(${interpolate(absorb, [0, 1], [1, .72], clamp)})`}}><EvidenceToken large /></div>
      <div style={{position: "absolute", left: 215, top: 216, opacity: progress(frame, 34, 66) * (1 - progress(frame, 218, 252)), transform: `scale(${interpolate(update, [0, 1], [.96, 1.02], clamp)})`}}><LearningState updated={update > .45} /></div>
      <div style={{position: "absolute", left: 1030, top: 260, width: 660, opacity: progress(frame, 70, 104) * (1 - progress(frame, 222, 250))}}>
        <div style={{display: "flex", alignItems: "center", gap: 20, fontSize: 26, color: T.muted, opacity: stages}}><span style={{color: T.ink}}>Observe</span><span>→</span><span style={{color: update > .45 ? T.ink : T.muted}}>Update State</span></div>
        <div style={{marginTop: 72, position: "relative", height: 160}}>
          <ProductCard style={{position: "absolute", inset: 0, padding: "32px 36px", opacity: 1 - replace, transform: `translateY(${replace * 32}px)`}}><div style={{fontSize: 18, color: T.muted}}>PLANNED</div><div style={{fontSize: 31, marginTop: 20}}>{COPY.oldNext}</div></ProductCard>
          <ProductCard style={{position: "absolute", inset: 0, padding: "32px 36px", opacity: replace, transform: `translateY(${(1 - replace) * -30}px)`, borderColor: T.accent}}><div style={{fontSize: 18, color: T.muted}}>ADAPTED</div><div style={{fontSize: 31, marginTop: 20}}>{COPY.newNext}</div></ProductCard>
        </div>
        <div style={{fontSize: 40, fontWeight: 500, marginTop: 55, opacity: replan}}>Re-plan</div>
      </div>
      <ProductCard style={{position: "absolute", left: 480, top: 175, width: 960, height: 690, overflow: "hidden", opacity: result, transform: `scale(${interpolate(result, [0, 1], [.72, 1], clamp)})`}}>
        <div style={{padding: "32px 40px", fontSize: 18, letterSpacing: ".1em", color: T.muted}}>NEXT · VISUAL EXPLANATION</div>
        <div style={{transform: "scale(.88)", transformOrigin: "top center"}}><PcaVisualization progressStart={238} /></div>
      </ProductCard>
      <div style={{position: "absolute", left: "50%", top: 454, transform: `translateX(-50%) scale(${interpolate(grid, [0, 1], [.82, 1], clamp)})`, display: "flex", gap: 16, opacity: grid}}>{SKILLS.map((skill) => <SkillCard key={skill} label={skill} selected={false} />)}</div>
    </AbsoluteFill>
  );
};
