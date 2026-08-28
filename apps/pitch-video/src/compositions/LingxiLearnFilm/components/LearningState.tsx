import {FILM_THEME as T} from "../theme";

export const LearningState = ({updated = false}: {updated?: boolean}) => (
  <div style={{position: "relative", width: 650, height: 420}}>
    <div style={{position: "absolute", left: 190, top: 80, width: 270, height: 270, borderRadius: "50%", background: T.ink, color: T.white, display: "flex", alignItems: "center", justifyContent: "center", textAlign: "center", fontSize: 31, lineHeight: 1.2, boxShadow: T.shadow}}>Learning<br />State</div>
    <div style={{position: "absolute", inset: 35, border: `1px solid ${T.line}`, borderRadius: "50%", transform: "scaleY(.52) rotate(-8deg)"}} />
    {[{label: "Current knowledge", x: 12, y: 160}, {label: "Weak concepts", x: 390, y: 8}, {label: "Learning goal", x: 420, y: 330}, {label: "Previous evidence", x: 10, y: 328}].map((n, i) => <div key={n.label} style={{position: "absolute", left: n.x, top: n.y, padding: "12px 16px", borderRadius: 12, border: `1px solid ${i === 1 && updated ? T.accent : T.line}`, background: i === 1 && updated ? T.accentSoft : T.white, fontSize: 17, boxShadow: "0 10px 26px rgba(0,0,0,.06)"}}>{n.label}</div>)}
  </div>
);
