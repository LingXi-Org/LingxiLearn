import {AbsoluteFill, Easing, Interactive, interpolate, useCurrentFrame} from "remotion";
import {SpatialState} from "../components/SpatialState";

export const Scene01SpatialIntro: React.FC = () => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{backgroundColor: "#07090C", color: "white", overflow: "hidden"}}>
      <SpatialState />
      <AbsoluteFill style={{background: "radial-gradient(circle at 50% 50%, transparent 0%, rgba(7,9,12,.22) 44%, rgba(7,9,12,.88) 100%)"}} />
      <Interactive.Div
        name="Opening eyebrow"
        style={{position: "absolute", left: 96, top: 94, fontSize: 20, letterSpacing: ".18em", color: "#C8FF45", opacity: interpolate(frame, [8, 28], [0, 1], {extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.bezier(.16, 1, .3, 1)})}}
      >
        THE LEARNING STATE
      </Interactive.Div>
      <Interactive.Div
        name="Opening title"
        style={{position: "absolute", left: 92, bottom: 128, width: 1100, fontSize: 105, lineHeight: .98, letterSpacing: "-.065em", fontWeight: 600, opacity: interpolate(frame, [18, 48, 254, 286], [0, 1, 1, 0], {extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: [Easing.bezier(.16, 1, .3, 1), Easing.linear, Easing.bezier(.7, 0, .84, 0)]}), translate: interpolate(frame, [18, 48], ["0px 44px", "0px 0px"], {extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.bezier(.16, 1, .3, 1)})}}
      >
        AI 不只回答问题。<br /><span style={{color: "#C8FF45"}}>它理解学习如何发生。</span>
      </Interactive.Div>
      <Interactive.Div name="Opening descriptor" style={{position: "absolute", right: 96, bottom: 108, width: 390, fontSize: 24, lineHeight: 1.5, color: "rgba(255,255,255,.64)", opacity: interpolate(frame, [56, 82], [0, 1], {extrapolateLeft: "clamp", extrapolateRight: "clamp"})}}>
        目标、掌握度、误区与证据<br />共同构成持续更新的学习状态。
      </Interactive.Div>
    </AbsoluteFill>
  );
};
