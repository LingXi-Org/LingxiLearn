import {BlurMask, Circle, LinearGradient, Rect, vec} from "@shopify/react-native-skia";
import {SkiaCanvas} from "@remotion/skia";
import {AbsoluteFill, Easing, interpolate, useCurrentFrame} from "remotion";

const clamp = {extrapolateLeft: "clamp", extrapolateRight: "clamp"} as const;

export const Scene03SkiaBrand: React.FC = () => {
  const frame = useCurrentFrame();
  const reveal = interpolate(frame, [8, 70], [0, 1], {...clamp, easing: Easing.bezier(.16, 1, .3, 1)});

  return (
    <AbsoluteFill style={{backgroundColor: "#07090C"}}>
      <SkiaCanvas width={1920} height={1080}>
        <Rect x={0} y={0} width={1920} height={1080}>
          <LinearGradient start={vec(0, 0)} end={vec(1920, 1080)} colors={["#07090C", "#111821", "#07090C"]} />
        </Rect>
        <Circle cx={780} cy={500} r={interpolate(frame, [0, 82], [120, 570], clamp)} color="rgba(83,207,255,.14)"><BlurMask blur={108} style="normal" /></Circle>
        <Circle cx={1260} cy={410} r={interpolate(frame, [0, 82], [80, 410], clamp)} color="rgba(180,255,173,.13)"><BlurMask blur={94} style="normal" /></Circle>
      </SkiaCanvas>

      <svg viewBox="0 0 1920 1080" width="1920" height="1080" style={{position: "absolute", inset: 0, overflow: "visible"}}>
        <defs>
          <linearGradient id="glass-script" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor="#73D8FF" stopOpacity=".82" />
            <stop offset=".3" stopColor="#F8FCFF" stopOpacity=".94" />
            <stop offset=".62" stopColor="#C5EFFF" stopOpacity=".68" />
            <stop offset="1" stopColor="#A9FFD0" stopOpacity=".78" />
          </linearGradient>
          <linearGradient id="glass-highlight" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#FFFFFF" stopOpacity="1" />
            <stop offset=".45" stopColor="#FFFFFF" stopOpacity=".5" />
            <stop offset="1" stopColor="#D4F7FF" stopOpacity=".86" />
          </linearGradient>
          <filter id="wide-glow" x="-30%" y="-60%" width="160%" height="220%"><feGaussianBlur stdDeviation="18" /></filter>
          <filter id="soft-glow" x="-25%" y="-50%" width="150%" height="200%"><feGaussianBlur stdDeviation="7" /></filter>
          <clipPath id="handwriting-reveal"><rect x="90" y="180" width={1740 * reveal} height="600" rx="40" /></clipPath>
        </defs>
        <g clipPath="url(#handwriting-reveal)">
          <text x="960" y="625" textAnchor="middle" fontFamily="'Brush Script MT', 'Snell Roundhand', cursive" fontSize="310" fontWeight="400" letterSpacing="2" fill="none" stroke="rgba(74,210,255,.44)" strokeWidth="28" strokeLinejoin="round" strokeLinecap="round" filter="url(#wide-glow)">LingxiLearn</text>
          <text x="960" y="625" textAnchor="middle" fontFamily="'Brush Script MT', 'Snell Roundhand', cursive" fontSize="310" fontWeight="400" letterSpacing="2" fill="rgba(224,248,255,.08)" stroke="url(#glass-script)" strokeWidth="14" strokeLinejoin="round" strokeLinecap="round" filter="url(#soft-glow)">LingxiLearn</text>
          <text x="960" y="625" textAnchor="middle" fontFamily="'Brush Script MT', 'Snell Roundhand', cursive" fontSize="310" fontWeight="400" letterSpacing="2" fill="rgba(211,243,255,.13)" stroke="url(#glass-script)" strokeWidth="8" strokeLinejoin="round" strokeLinecap="round">LingxiLearn</text>
          <text x="960" y="625" textAnchor="middle" fontFamily="'Brush Script MT', 'Snell Roundhand', cursive" fontSize="310" fontWeight="400" letterSpacing="2" fill="none" stroke="url(#glass-highlight)" strokeWidth="2.2" strokeLinejoin="round" strokeLinecap="round">LingxiLearn</text>
        </g>
      </svg>

      <div style={{position: "absolute", left: 0, right: 0, top: 700, textAlign: "center", color: "#C8FF45", fontSize: 34, letterSpacing: ".06em", opacity: interpolate(frame, [70, 88], [0, 1], clamp)}}>AI 学习，因你而变。</div>
      <div style={{position: "absolute", left: 0, right: 0, bottom: 82, textAlign: "center", color: "rgba(255,255,255,.46)", fontSize: 24, letterSpacing: ".08em", opacity: interpolate(frame, [88, 103], [0, 1], clamp)}}>LINGXILEARN.CN</div>
    </AbsoluteFill>
  );
};
