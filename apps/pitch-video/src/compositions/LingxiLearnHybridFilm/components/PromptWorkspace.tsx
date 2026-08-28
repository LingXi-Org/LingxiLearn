import type {ReactNode} from "react";
import {COPY} from "../../LingxiLearnFilm/copy";
import {FILM_THEME as T} from "../../LingxiLearnFilm/theme";

export const PromptWorkspace = ({children, activeStep}: {children: ReactNode; activeStep: number}) => {
  const steps = ["Act", "Observe", "Update State", "Re-plan", "New next step"];
  const goalLines = COPY.goal.split("，");
  return (
    <div style={{position: "absolute", inset: 52, borderRadius: 32, overflow: "hidden", background: T.white, boxShadow: T.shadow, display: "grid", gridTemplateColumns: "37% 63%"}}>
      <div style={{background: T.ink, color: T.white, padding: "42px 40px", position: "relative"}}>
        <div style={{display: "flex", alignItems: "center", gap: 13, fontSize: 24, fontWeight: 600}}><span style={{width: 34, height: 34, borderRadius: 10, background: T.accent, color: T.ink, display: "grid", placeItems: "center"}}>L</span>LingxiLearn</div>
        <div style={{marginTop: 115, fontSize: 17, color: "rgba(255,255,255,.44)", letterSpacing: ".12em"}}>YOUR LEARNING GOAL</div>
        <div style={{marginTop: 24, minHeight: 185, border: "1px solid rgba(255,255,255,.17)", background: "rgba(255,255,255,.06)", borderRadius: 22, padding: "27px 28px", fontSize: 29, lineHeight: 1.5}}>{goalLines[0]}，<br />{goalLines[1]}</div>
        <div style={{marginTop: 18, display: "inline-flex", alignItems: "center", gap: 10, padding: "11px 15px", borderRadius: 999, background: "rgba(207,255,61,.12)", color: T.accent, fontSize: 17}}><span style={{width: 8, height: 8, borderRadius: 99, background: T.accent}} />Goal committed</div>
        <div style={{position: "absolute", left: 40, right: 40, bottom: 42, fontSize: 16, color: "rgba(255,255,255,.35)", display: "flex", justifyContent: "space-between"}}><span>State-aware learning</span><span>Goal → Experience</span></div>
      </div>
      <div style={{padding: "38px 40px", position: "relative", background: "#FBFBF8"}}>
        <div style={{display: "flex", justifyContent: "space-between", alignItems: "end"}}><div><div style={{fontSize: 17, color: T.muted, letterSpacing: ".12em"}}>LIVE LEARNING EXPERIENCE</div><div style={{fontSize: 25, marginTop: 8}}>系统根据当前学习状态决定下一步</div></div><div style={{fontSize: 15, padding: "9px 13px", borderRadius: 999, background: T.soft, color: T.muted}}>LIVE</div></div>
        <div style={{display: "grid", gridTemplateColumns: "repeat(5,1fr)", gap: 8, marginTop: 26}}>{steps.map((step, index) => <div key={step} style={{height: 44, borderRadius: 12, display: "grid", placeItems: "center", background: index === activeStep ? T.ink : index < activeStep ? T.accentSoft : T.soft, color: index === activeStep ? T.white : index < activeStep ? T.ink : T.muted, borderBottom: index === activeStep ? `3px solid ${T.accent}` : "3px solid transparent", fontSize: 15}}>{step}</div>)}</div>
        <div style={{position: "absolute", left: 40, right: 40, top: 168, bottom: 38, borderRadius: 26, border: `1px solid ${T.line}`, background: T.white, overflow: "hidden"}}>{children}</div>
      </div>
    </div>
  );
};
