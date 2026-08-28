import {interpolate, useCurrentFrame} from "remotion";
import {clamp, progress} from "../utils/animation";
import {FILM_THEME as T} from "../theme";

const points = [
  [-235, 94], [-206, 72], [-183, 54], [-161, 85], [-135, 39], [-108, 51], [-82, 15], [-52, 24], [-27, -3], [5, 7], [31, -30], [62, -17], [87, -57], [116, -46], [144, -86], [176, -72], [207, -112], [235, -92],
  [-188, 122], [-145, 91], [-102, 82], [-63, 52], [-18, 35], [23, 28], [67, -5], [103, -15], [148, -50], [191, -45],
] as const;

export const PcaVisualization = ({progressStart = 0}: {progressStart?: number}) => {
  const frame = useCurrentFrame();
  const axis = progress(frame, progressStart + 12, progressStart + 48);
  const projection = progress(frame, progressStart + 46, progressStart + 80);
  return (
    <svg width="920" height="510" viewBox="0 0 920 510">
      <line x1="90" y1="420" x2="830" y2="420" stroke={T.line} strokeWidth="2" />
      <line x1="90" y1="420" x2="90" y2="76" stroke={T.line} strokeWidth="2" />
      <line x1="155" y1="390" x2={155 + 610 * axis} y2={390 - 290 * axis} stroke={T.ink} strokeWidth="5" strokeLinecap="round" />
      <text x="690" y="106" fontSize="21" fill={T.ink} opacity={axis}>principal direction</text>
      {points.map(([x, y], i) => {
        const cx = 460 + x;
        const cy = 255 + y;
        const projectedX = 460 + x * 0.82 - y * 0.39;
        const projectedY = 255 - (projectedX - 460) * 0.475;
        const px = interpolate(projection, [0, 1], [cx, projectedX], clamp);
        const py = interpolate(projection, [0, 1], [cy, projectedY], clamp);
        return <g key={i}><line x1={cx} y1={cy} x2={px} y2={py} stroke={T.violet} strokeOpacity={projection * 0.34} strokeWidth="1.5" /><circle cx={px} cy={py} r="7" fill={i % 3 === 0 ? T.violet : T.cyan} opacity={0.8 + (i % 3) * 0.08} /></g>;
      })}
    </svg>
  );
};
