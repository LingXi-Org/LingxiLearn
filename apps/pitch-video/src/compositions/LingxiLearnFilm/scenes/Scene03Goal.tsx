import {AbsoluteFill, interpolate, useCurrentFrame} from "remotion";
import {GoalCard, ProductCard} from "../components/Cards";
import {COPY} from "../copy";
import {FILM_THEME as T} from "../theme";
import {clamp, enter, progress} from "../utils/animation";

const chunks = ["我想真正理解 PCA，", "并能够独立做题。"];

export const Scene03Goal: React.FC = () => {
  const frame = useCurrentFrame();
  const input = enter(frame, 0, 25) * (1 - progress(frame, 154, 190));
  const submit = progress(frame, 112, 126);
  const card = progress(frame, 154, 196);
  return (
    <AbsoluteFill style={{background: T.paper, alignItems: "center", overflow: "hidden"}}>
      <div style={{position: "absolute", top: 150, fontSize: 18, letterSpacing: ".14em", color: T.muted}}>FROM ONE REAL GOAL</div>
      <ProductCard style={{position: "absolute", top: 338, width: 1120, height: 250, padding: "34px 40px", opacity: input, transform: `scale(${interpolate(input, [0, 1], [.96, 1], clamp)})`}}>
        <div style={{fontSize: 16, color: T.muted}}>Ask LingxiLearn</div>
        <div style={{fontSize: 37, marginTop: 28, lineHeight: 1.35}}>{chunks.map((chunk, i) => <span key={chunk} style={{opacity: progress(frame, 38 + i * 35, 58 + i * 35)}}>{chunk}</span>)}</div>
        <div style={{position: "absolute", right: 34, bottom: 30, width: 54, height: 54, borderRadius: 17, background: T.ink, color: T.white, display: "flex", alignItems: "center", justifyContent: "center", transform: `scale(${interpolate(submit, [0, .5, 1], [1, .88, 1], clamp)})`, fontSize: 28}}>↑</div>
      </ProductCard>
      <div style={{position: "absolute", top: interpolate(card, [0, 1], [385, 412], clamp), opacity: card, transform: `scale(${interpolate(card, [0, 1], [1.45, 1], clamp)})`}}><GoalCard compact /></div>
      <div style={{position: "absolute", bottom: 145, fontSize: 25, color: T.muted, opacity: enter(frame, 70, 24) * (1 - card)}}>{COPY.goal}</div>
    </AbsoluteFill>
  );
};
