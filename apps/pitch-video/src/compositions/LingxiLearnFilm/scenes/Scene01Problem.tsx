import {AbsoluteFill, interpolate, useCurrentFrame} from "remotion";
import {COPY} from "../copy";
import {FILM_THEME as T} from "../theme";
import {clamp, enter, progress} from "../utils/animation";

export const Scene01Problem: React.FC = () => {
  const frame = useCurrentFrame();
  const title = enter(frame, 4, 30);
  const grid = progress(frame, 44, 68) * (1 - progress(frame, 98, 128));
  const morph = progress(frame, 96, 136);
  const rows = Array.from({length: 15}, (_, i) => i);
  return (
    <AbsoluteFill style={{background: T.paper, alignItems: "center", overflow: "hidden"}}>
      <div style={{position: "absolute", top: 166, fontSize: 90, fontWeight: 500, letterSpacing: "-.06em", opacity: title * (1 - morph), filter: `blur(${(1 - title) * 9}px)`, transform: `translateY(${(1 - title) * 28}px)`}}>{COPY.problem}</div>
      <div style={{position: "absolute", inset: "355px 120px auto", display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: "24px 42px", opacity: grid, transform: `scale(${interpolate(morph, [0, 1], [1, .42], clamp)})`, transformOrigin: "50% 30%"}}>
        {rows.map((i) => <div key={i} style={{fontSize: 27, color: i % 4 === 0 ? T.ink : T.muted, whiteSpace: "nowrap", textAlign: "center"}}>{COPY.sameAnswer}</div>)}
      </div>
      <div style={{position: "absolute", left: "50%", top: interpolate(morph, [0, 1], [620, 478], clamp), width: interpolate(morph, [0, 1], [1260, 620], clamp), minHeight: interpolate(morph, [0, 1], [0, 150], clamp), transform: `translateX(-50%) scale(${interpolate(morph, [0, 1], [.88, 1], clamp)})`, borderRadius: 28, background: T.white, border: `1px solid ${T.line}`, boxShadow: T.shadow, padding: "34px 42px", opacity: morph * (1 - progress(frame, 136, 149))}}>
        <div style={{fontSize: 16, color: T.muted}}>AI</div><div style={{fontSize: 27, marginTop: 12}}>这里是一个标准答案。</div>
      </div>
    </AbsoluteFill>
  );
};
