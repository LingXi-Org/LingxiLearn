import {AbsoluteFill, interpolate, useCurrentFrame} from "remotion";
import {EvidenceToken} from "../../LingxiLearnFilm/components/Cards";
import {PcaVisualization} from "../../LingxiLearnFilm/components/PcaVisualization";
import {COPY} from "../../LingxiLearnFilm/copy";
import {FILM_THEME as T} from "../../LingxiLearnFilm/theme";
import {clamp, progress} from "../../LingxiLearnFilm/utils/animation";
import {PromptWorkspace} from "../components/PromptWorkspace";

export const Scene05PromptExperience: React.FC = () => {
  const frame = useCurrentFrame();
  const visualize = 1 - progress(frame, 82, 108);
  const variance = progress(frame, 80, 108) * (1 - progress(frame, 132, 160));
  const explain = progress(frame, 128, 158) * (1 - progress(frame, 192, 216));
  const practice = progress(frame, 188, 220) * (1 - progress(frame, 286, 315));
  const wrong = progress(frame, 252, 270);
  const evidence = progress(frame, 280, 324);
  const activeStep = frame < 280 ? 0 : 1;
  return (
    <AbsoluteFill style={{background: T.paper}}>
      <PromptWorkspace activeStep={activeStep}>
        <div style={{position: "absolute", inset: 0, opacity: visualize}}><div style={{position: "absolute", left: 26, top: 18, transform: "scale(.73)", transformOrigin: "top left"}}><PcaVisualization /></div><div style={{position: "absolute", right: 40, top: 86, width: 330}}><div style={{fontSize: 41, lineHeight: 1.05, fontWeight: 500}}>{COPY.pcaHint}</div><div style={{fontSize: 19, color: T.muted, lineHeight: 1.5, marginTop: 22}}>点云向主方向投影，学习产物从目标自然生成。</div></div></div>
        <div style={{position: "absolute", inset: 0, display: "grid", placeItems: "center", opacity: variance, transform: `scale(${interpolate(variance, [0, 1], [.82, 1.05], clamp)})`}}><div style={{fontSize: 104, fontWeight: 500, letterSpacing: "-.07em"}}>{COPY.variance}</div></div>
        <div style={{position: "absolute", inset: 32, borderRadius: 22, border: `1px solid ${T.line}`, padding: "38px 44px", opacity: explain, transform: `scale(${interpolate(explain, [0, 1], [.94, 1], clamp)})`}}><div style={{fontSize: 17, color: T.muted, letterSpacing: ".1em"}}>UNDERSTAND VARIANCE</div><div style={{fontSize: 66, fontWeight: 500, marginTop: 45}}>{COPY.formula}</div><div style={{fontSize: 27, color: T.muted, marginTop: 32}}>{COPY.formulaHint}</div><div style={{position: "absolute", right: 40, bottom: 38, padding: "13px 18px", borderRadius: 999, background: T.ink, color: T.white, fontSize: 19}}>{COPY.practice} →</div></div>
        <div style={{position: "absolute", inset: 28, borderRadius: 22, border: `1px solid ${T.line}`, padding: "34px 38px", opacity: practice, transform: `scale(${interpolate(practice, [0, 1], [.94, 1], clamp)})`}}><div style={{fontSize: 16, color: T.muted, letterSpacing: ".1em"}}>TRY IT YOURSELF</div><div style={{fontSize: 38, fontWeight: 500, marginTop: 30}}>{COPY.question}</div><div style={{display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14, marginTop: 32}}>{["变化最大的方向", "离原点最近的方向", "维度最多的方向", "平均值最大的方向"].map((option, index) => <div key={option} style={{padding: "19px 20px", borderRadius: 15, border: `1px solid ${index === 1 && wrong ? T.coral : T.line}`, background: index === 1 && wrong ? "#FFF2EE" : T.white, fontSize: 21, color: index === 1 && wrong ? "#9F3C24" : T.ink}}>{option}</div>)}</div><div style={{fontSize: 18, color: T.muted, marginTop: 22, opacity: wrong}}>{COPY.wrong}</div></div>
        <div style={{position: "absolute", left: "50%", top: interpolate(evidence, [0, 1], [520, 270], clamp), transform: `translateX(-50%) scale(${interpolate(evidence, [0, 1], [.76, 1], clamp)})`, opacity: evidence}}><EvidenceToken large /></div>
      </PromptWorkspace>
    </AbsoluteFill>
  );
};
