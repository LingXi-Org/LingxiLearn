import {AbsoluteFill, interpolate, useCurrentFrame} from "remotion";
import {BrandLogo} from "../components/BrandLogo";
import {FILM_THEME as T} from "../theme";
import {clamp, enter, progress} from "../utils/animation";

export const Scene02BrandPremise: React.FC = () => {
  const frame = useCurrentFrame();
  const question = enter(frame, 6, 26) * (1 - progress(frame, 116, 145));
  const rearrange = progress(frame, 56, 92);
  const logo = progress(frame, 100, 126) * (1 - progress(frame, 136, 149));
  return (
    <AbsoluteFill style={{background: T.paper, alignItems: "center", justifyContent: "center", overflow: "hidden"}}>
      <div style={{fontSize: 82, fontWeight: 500, letterSpacing: "-.06em", opacity: question, transform: `translateY(${(1 - question) * 25}px)`, whiteSpace: "nowrap"}}>
        如果 AI 能真正<span style={{display: "inline-block", padding: `0 ${interpolate(rearrange, [0, 1], [0, 15], clamp)}px`, color: rearrange > .5 ? T.ink : T.muted, background: `linear-gradient(transparent 72%, ${T.accentSoft} 72%)`, verticalAlign: "baseline"}}>理解</span>你如何<span style={{display: "inline", verticalAlign: "baseline"}}>学习</span>？
      </div>
      <div style={{position: "absolute", top: 650, opacity: logo, transform: `scale(${interpolate(logo, [0, 1], [.94, 1], clamp)})`}}><BrandLogo width={270} /></div>
      <div style={{position: "absolute", left: "50%", top: 807, width: interpolate(progress(frame, 132, 149), [0, 1], [76, 760], clamp), height: 3, transform: "translateX(-50%)", background: T.ink, borderRadius: 99, opacity: progress(frame, 126, 142)}} />
    </AbsoluteFill>
  );
};
