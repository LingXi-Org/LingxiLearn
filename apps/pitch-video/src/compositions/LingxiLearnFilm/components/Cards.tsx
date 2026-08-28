import type {ReactNode} from "react";
import {FILM_THEME as T} from "../theme";

export const ProductCard = ({children, style}: {children: ReactNode; style?: React.CSSProperties}) => (
  <div style={{background: T.white, border: `1px solid ${T.line}`, borderRadius: T.radius, boxShadow: T.shadow, ...style}}>{children}</div>
);

export const GoalCard = ({compact = false}: {compact?: boolean}) => (
  <ProductCard style={{width: compact ? 390 : 760, padding: compact ? "23px 28px" : "28px 34px"}}>
    <div style={{fontSize: 15, letterSpacing: ".13em", color: T.muted, fontWeight: 600}}>GOAL</div>
    <div style={{fontSize: compact ? 27 : 34, marginTop: 10, fontWeight: 500}}>Understand PCA</div>
  </ProductCard>
);

export const SkillCard = ({label, selected = false}: {label: string; selected?: boolean}) => (
  <div style={{width: 220, height: 98, borderRadius: 20, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 23, fontWeight: 500, background: selected ? T.ink : T.white, color: selected ? T.white : T.ink, border: `1px solid ${selected ? T.ink : T.line}`, boxShadow: selected ? "0 22px 55px rgba(0,0,0,.2)" : "none"}}>{label}</div>
);

export const EvidenceToken = ({large = false}: {large?: boolean}) => (
  <div style={{display: "inline-flex", alignItems: "center", gap: 12, padding: large ? "18px 24px" : "12px 17px", borderRadius: 999, background: T.accentSoft, border: `1px solid ${T.accent}`, fontSize: large ? 24 : 18, fontWeight: 500}}><span style={{width: 10, height: 10, borderRadius: "50%", background: T.ink}} />Evidence</div>
);
