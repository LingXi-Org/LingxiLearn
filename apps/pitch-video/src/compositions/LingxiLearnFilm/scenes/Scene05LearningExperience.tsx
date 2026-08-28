import {AbsoluteFill, interpolate, useCurrentFrame} from "remotion";
import {EvidenceToken, ProductCard} from "../components/Cards";
import {PcaVisualization} from "../components/PcaVisualization";
import {COPY} from "../copy";
import {FILM_THEME as T} from "../theme";
import {clamp, progress} from "../utils/animation";

export const Scene05LearningExperience: React.FC = () => {
  const frame = useCurrentFrame();
  const artifact = 1 - progress(frame, 82, 108);
  const variance = progress(frame, 80, 108) * (1 - progress(frame, 132, 160));
  const explain = progress(frame, 128, 158) * (1 - progress(frame, 192, 216));
  const practice = progress(frame, 188, 220) * (1 - progress(frame, 286, 315));
  const wrong = progress(frame, 252, 270);
  const evidence = progress(frame, 280, 324);
  return (
    <AbsoluteFill style={{background: T.paper, overflow: "hidden"}}>
      <ProductCard style={{position: "absolute", left: 135, top: 118, width: 1650, height: 844, overflow: "hidden", opacity: artifact}}>
        <div style={{position: "absolute", left: 54, top: 40, fontSize: 18, letterSpacing: ".12em", color: T.muted}}>VISUAL EXPLANATION · PCA</div>
        <div style={{position: "absolute", left: 78, top: 120}}><PcaVisualization progressStart={0} /></div>
        <div style={{position: "absolute", right: 90, top: 255, width: 460}}><div style={{fontSize: 52, fontWeight: 500, letterSpacing: "-.05em"}}>{COPY.pcaHint}</div><div style={{fontSize: 22, color: T.muted, marginTop: 28, lineHeight: 1.55}}>投影不是压缩细节，而是寻找最能表达数据变化的方向。</div></div>
      </ProductCard>

      <div style={{position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", opacity: variance, transform: `scale(${interpolate(variance, [0, 1], [.84, 1.08], clamp)})`}}><div style={{fontSize: 132, fontWeight: 500, letterSpacing: "-.07em"}}>{COPY.variance}</div></div>

      <ProductCard style={{position: "absolute", left: 390, top: 270, width: 1140, height: 510, padding: "54px 64px", opacity: explain, transform: `scale(${interpolate(explain, [0, 1], [.94, 1], clamp)})`}}>
        <div style={{fontSize: 20, color: T.muted, letterSpacing: ".1em"}}>UNDERSTAND VARIANCE</div>
        <div style={{fontSize: 74, fontWeight: 500, marginTop: 62}}>{COPY.formula}</div>
        <div style={{fontSize: 30, color: T.muted, marginTop: 46}}>{COPY.formulaHint}</div>
        <div style={{position: "absolute", right: 58, bottom: 50, fontSize: 21, padding: "14px 20px", borderRadius: 999, background: T.ink, color: T.white}}>{COPY.practice} →</div>
      </ProductCard>

      <ProductCard style={{position: "absolute", left: 420, top: 216, width: 1080, height: 610, padding: "48px 56px", opacity: practice, transform: `scale(${interpolate(practice, [0, 1], [.94, 1], clamp)})`}}>
        <div style={{fontSize: 18, color: T.muted, letterSpacing: ".1em"}}>TRY IT YOURSELF</div>
        <div style={{fontSize: 48, fontWeight: 500, marginTop: 45}}>{COPY.question}</div>
        <div style={{display: "grid", gridTemplateColumns: "1fr 1fr", gap: 18, marginTop: 55}}>
          {["变化最大的方向", "离原点最近的方向", "维度最多的方向", "平均值最大的方向"].map((option, i) => <div key={option} style={{padding: "22px 25px", borderRadius: 17, border: `1px solid ${i === 1 && wrong ? T.coral : T.line}`, background: i === 1 && wrong ? "#fff2ee" : T.white, fontSize: 24, color: i === 1 && wrong ? "#9f3c24" : T.ink}}>{option}</div>)}
        </div>
        <div style={{marginTop: 31, fontSize: 21, color: T.muted, opacity: wrong}}>{COPY.wrong}</div>
      </ProductCard>

      <div style={{position: "absolute", left: "50%", top: interpolate(evidence, [0, 1], [690, 486], clamp), transform: `translateX(-50%) scale(${interpolate(evidence, [0, 1], [.75, 1], clamp)})`, opacity: evidence}}><EvidenceToken large /></div>
    </AbsoluteFill>
  );
};
