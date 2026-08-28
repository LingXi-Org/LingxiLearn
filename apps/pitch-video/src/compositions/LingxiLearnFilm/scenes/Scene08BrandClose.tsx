import {AbsoluteFill, interpolate, useCurrentFrame} from "remotion";
import {BrandLogo} from "../components/BrandLogo";
import {COPY} from "../copy";
import {FILM_THEME as T} from "../theme";
import {clamp, progress} from "../utils/animation";

export const Scene08BrandClose: React.FC = () => {
  const frame = useCurrentFrame();
  const logo = progress(frame, 20, 52);
  const tagline = progress(frame, 60, 86);
  return (
    <AbsoluteFill style={{background: T.ink, color: T.white, alignItems: "center", justifyContent: "center"}}>
      <div style={{filter: "none", opacity: logo, transform: `translateY(${interpolate(tagline, [0, 1], [26, -20], clamp)}) scale(${interpolate(logo, [0, 1], [.9, 1], clamp)})`}}><BrandLogo width={400} dark={false} /></div>
      <div style={{fontSize: 45, marginTop: 55, fontWeight: 500, letterSpacing: "-.04em", opacity: tagline, transform: `translateY(${interpolate(tagline, [0, 1], [18, 0], clamp)})`}}>{COPY.tagline}</div>
      <div style={{position: "absolute", bottom: 54, fontSize: 16, letterSpacing: ".08em", color: "rgba(255,255,255,.38)", opacity: tagline}}>lingxilearn.cn</div>
    </AbsoluteFill>
  );
};
