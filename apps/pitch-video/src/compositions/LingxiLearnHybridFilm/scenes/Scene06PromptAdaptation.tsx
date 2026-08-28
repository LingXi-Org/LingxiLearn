import {AbsoluteFill, Easing, interpolate, useCurrentFrame} from "remotion";
import {EvidenceToken} from "../../LingxiLearnFilm/components/Cards";
import {LearningState} from "../../LingxiLearnFilm/components/LearningState";
import {PcaVisualization} from "../../LingxiLearnFilm/components/PcaVisualization";
import {COPY} from "../../LingxiLearnFilm/copy";
import {FILM_THEME as T} from "../../LingxiLearnFilm/theme";
import {clamp, progress} from "../../LingxiLearnFilm/utils/animation";
import {PromptWorkspace} from "../components/PromptWorkspace";

export const Scene06PromptAdaptation: React.FC = () => {
  const frame = useCurrentFrame();
  const absorb = interpolate(frame, [0, 68], [0, 1], {
    ...clamp,
    easing: Easing.inOut(Easing.cubic),
  });
  const update = progress(frame, 70, 112);
  const replace = progress(frame, 150, 214);
  const result = progress(frame, 226, 282);
  const activeStep = frame < 72 ? 1 : frame < 150 ? 2 : frame < 226 ? 3 : 4;
  return (
    <AbsoluteFill style={{background: T.paper}}>
      <PromptWorkspace activeStep={activeStep}>
        <div style={{position: "absolute", inset: 0, opacity: 1 - progress(frame, 214, 242)}}>
          <div style={{position: "absolute", left: interpolate(absorb, [0, 1], [452, 160], clamp), top: interpolate(absorb, [0, 1], [270, 282], clamp), opacity: 1 - progress(frame, 70, 90), transform: `scale(${interpolate(absorb, [0, 1], [1, .7], clamp)})`}}><EvidenceToken large /></div>
          <div style={{position: "absolute", left: 18, top: 104, transform: "scale(.66)", transformOrigin: "top left", opacity: progress(frame, 30, 62)}}><LearningState updated={update > .45} /></div>
          <div style={{position: "absolute", right: 34, top: 62, width: 465, opacity: progress(frame, 68, 100)}}><div style={{display: "flex", alignItems: "center", gap: 14, fontSize: 21, color: T.muted}}><span style={{color: T.ink}}>Observe</span><span>→</span><span style={{color: update > .45 ? T.ink : T.muted}}>Update State</span></div><div style={{position: "relative", height: 190, marginTop: 44}}><div style={{position: "absolute", inset: 0, padding: "28px 30px", borderRadius: 20, border: `1px solid ${T.line}`, background: T.white, opacity: 1 - replace, transform: `translateY(${replace * 26}px)`}}><div style={{fontSize: 16, color: T.muted}}>PLANNED</div><div style={{fontSize: 27, marginTop: 20}}>{COPY.oldNext}</div></div><div style={{position: "absolute", inset: 0, padding: "28px 30px", borderRadius: 20, border: `1px solid ${T.accent}`, background: T.white, opacity: replace, transform: `translateY(${(1 - replace) * -25}px)`}}><div style={{fontSize: 16, color: T.muted}}>ADAPTED</div><div style={{fontSize: 27, marginTop: 20}}>{COPY.newNext}</div></div></div><div style={{fontSize: 36, fontWeight: 500, marginTop: 32, opacity: progress(frame, 196, 226)}}>Re-plan</div></div>
        </div>
        <div style={{position: "absolute", inset: 28, borderRadius: 23, background: T.white, color: T.ink, border: `1px solid ${T.accent}`, opacity: result, transform: `scale(${interpolate(result, [0, 1], [.78, 1], clamp)})`, overflow: "hidden"}}><div style={{padding: "28px 34px", fontSize: 16, color: T.muted, letterSpacing: ".1em"}}>NEXT · VISUAL EXPLANATION</div><div style={{position: "absolute", left: 30, top: 78, transform: "scale(.72)", transformOrigin: "top left"}}><PcaVisualization progressStart={230} /></div><div style={{position: "absolute", right: 42, top: 155, width: 330, fontSize: 38, lineHeight: 1.1}}>先看见投影，<br />再理解最大方差。</div></div>
      </PromptWorkspace>
    </AbsoluteFill>
  );
};
