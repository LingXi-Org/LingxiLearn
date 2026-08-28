import {AbsoluteFill, Easing, Interactive, interpolate, useCurrentFrame} from "remotion";
import {H} from "../theme";

const stages = ["答错", "获取证据", "更新状态", "重新规划", "生成新路径"];

const stageForFrame = (frame: number) => {
  if (frame < 230) return 0;
  if (frame < 430) return 1;
  if (frame < 650) return 2;
  if (frame < 870) return 3;
  return 4;
};

const ResultPanel: React.FC<{stage: number; frame: number}> = ({stage, frame}) => {
  if (stage === 0) {
    return <div style={{display: "grid", gap: 18}}><div style={{fontSize: 29, color: H.muted}}>PCA 中，第一主成分的方向是：</div>{["使投影方差最大", "使投影距离最小", "与所有样本垂直"].map((item, index) => <div key={item} style={{height: 84, borderRadius: 18, border: `2px solid ${index === 1 ? H.red : H.line}`, background: index === 1 ? "#FFF1F1" : "white", display: "flex", alignItems: "center", padding: "0 28px", fontSize: 27}}><span style={{width: 38, height: 38, borderRadius: 99, border: `2px solid ${index === 1 ? H.red : H.line}`, marginRight: 20, display: "grid", placeItems: "center"}}>{index === 1 ? "×" : ""}</span>{item}</div>)}</div>;
  }
  if (stage === 1) {
    return <div style={{display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24}}><div style={{borderRadius: 24, padding: 30, background: "#101216", color: "white", minHeight: 330}}><div style={{fontSize: 19, color: H.lime, letterSpacing: ".1em"}}>NEW EVIDENCE</div><div style={{fontSize: 40, lineHeight: 1.15, marginTop: 54}}>误把“最小重构误差”<br />当成方向定义</div><div style={{marginTop: 48, color: "rgba(255,255,255,.55)", fontSize: 22}}>置信度 0.91</div></div><div style={{borderRadius: 24, padding: 30, border: `1px solid ${H.line}`, minHeight: 330}}><div style={{fontSize: 19, color: H.muted, letterSpacing: ".1em"}}>OBSERVED FROM</div><div style={{fontSize: 34, lineHeight: 1.25, marginTop: 56}}>选择、停留时间<br />与解释路径</div><div style={{height: 10, borderRadius: 99, background: "#ECEDE8", marginTop: 54}}><div style={{height: "100%", width: `${interpolate(frame, [230, 410], [8, 91], {extrapolateLeft: "clamp", extrapolateRight: "clamp"})}%`, background: H.lime, borderRadius: 99}} /></div></div></div>;
  }
  if (stage === 2) {
    return <div><div style={{display: "flex", justifyContent: "space-between", alignItems: "end"}}><div><div style={{fontSize: 19, color: H.muted, letterSpacing: ".1em"}}>LEARNING STATE</div><div style={{fontSize: 48, marginTop: 14}}>状态已更新</div></div><div style={{fontSize: 22, color: H.muted}}>Evidence absorbed</div></div><div style={{display: "grid", gap: 26, marginTop: 62}}>{[["几何直觉", 34, H.red], ["方差理解", 52, H.lime], ["公式推导", 71, H.cyan]].map(([label, value, color]) => <div key={String(label)}><div style={{display: "flex", justifyContent: "space-between", fontSize: 24, marginBottom: 12}}><span>{label}</span><span>{value}%</span></div><div style={{height: 15, background: "#EAEBE6", borderRadius: 99}}><div style={{width: `${interpolate(frame, [430, 630], [8, Number(value)], {extrapolateLeft: "clamp", extrapolateRight: "clamp"})}%`, height: "100%", background: String(color), borderRadius: 99}} /></div></div>)}</div></div>;
  }
  if (stage === 3) {
    return <div><div style={{fontSize: 19, color: H.muted, letterSpacing: ".1em"}}>DYNAMIC RE-PLAN</div><div style={{display: "grid", gap: 20, marginTop: 44}}><div style={{padding: "28px 30px", borderRadius: 22, background: "#F0F1ED", color: "#A2A49F", fontSize: 29, textDecoration: "line-through"}}>Next · 进入高阶计算练习</div><div style={{padding: "32px 30px", borderRadius: 22, background: H.ink, color: "white", fontSize: 34, boxShadow: "0 30px 60px rgba(10,11,13,.18)"}}><span style={{color: H.lime, marginRight: 18}}>New Next</span>先建立二维投影直觉</div></div><div style={{display: "flex", alignItems: "center", gap: 16, marginTop: 54, fontSize: 22, color: H.muted}}><span style={{width: 12, height: 12, borderRadius: 99, background: H.lime, boxShadow: `0 0 0 ${interpolate(frame, [650, 850], [0, 16], {extrapolateLeft: "clamp", extrapolateRight: "clamp"})}px rgba(200,255,69,.15)`}} /> State decides next</div></div>;
  }
  return <div style={{display: "grid", gridTemplateColumns: "1.15fr .85fr", gap: 28}}><div style={{borderRadius: 26, background: H.ink, color: "white", padding: 34, minHeight: 380}}><div style={{fontSize: 18, letterSpacing: ".1em", color: H.lime}}>NEW LEARNING PATH</div><div style={{fontSize: 39, lineHeight: 1.2, marginTop: 46}}>先看见投影，<br />再理解最大方差。</div><svg viewBox="0 0 420 135" style={{width: "100%", marginTop: 42}}><line x1="28" y1="108" x2="382" y2="31" stroke="#C8FF45" strokeWidth="5" />{Array.from({length: 18}, (_, index) => <circle key={index} cx={40 + (index * 47) % 330} cy={35 + (index * 31) % 85} r="7" fill={index % 3 === 0 ? "#65E6FF" : "#FFFFFF"} opacity=".8" />)}</svg></div><div style={{display: "grid", gap: 18}}>{["可视化解释", "针对性练习", "即时反馈"].map((item, index) => <div key={item} style={{border: `1px solid ${H.line}`, borderRadius: 22, padding: 24, display: "flex", alignItems: "center", fontSize: 25, background: "white"}}><span style={{width: 38, height: 38, borderRadius: 12, background: index === 0 ? H.lime : "#ECEDE8", marginRight: 18, display: "grid", placeItems: "center", fontSize: 18}}>0{index + 1}</span>{item}</div>)}</div></div>;
};

export const Scene02PromptLoop: React.FC = () => {
  const frame = useCurrentFrame();
  const stage = stageForFrame(frame);
  const prompt = "我想真正理解 PCA，并能够独立做题。";
  const typed = prompt.slice(0, Math.floor(interpolate(frame, [18, 145], [0, prompt.length], {extrapolateLeft: "clamp", extrapolateRight: "clamp"})));
  return (
    <AbsoluteFill style={{backgroundColor: H.paper, color: H.ink, padding: 52}}>
      <div style={{height: "100%", borderRadius: 34, overflow: "hidden", background: H.panel, boxShadow: "0 35px 90px rgba(10,11,13,.14)", display: "grid", gridTemplateColumns: "42% 58%"}}>
        <Interactive.Div name="Prompt input column" style={{background: "#0C0E12", color: "white", padding: "44px 42px", position: "relative"}}>
          <div style={{display: "flex", alignItems: "center", gap: 14, fontSize: 25, fontWeight: 600}}><span style={{width: 36, height: 36, background: H.lime, color: H.ink, borderRadius: 10, display: "grid", placeItems: "center"}}>L</span> LingxiLearn</div>
          <div style={{marginTop: 118, fontSize: 18, letterSpacing: ".12em", color: "rgba(255,255,255,.45)"}}>YOUR LEARNING GOAL</div>
          <div style={{marginTop: 24, minHeight: 220, borderRadius: 24, border: "1px solid rgba(255,255,255,.15)", background: "rgba(255,255,255,.06)", padding: 30, fontSize: 34, lineHeight: 1.45}}>{typed}<span style={{display: frame % 22 < 12 ? "inline" : "none", color: H.lime}}>|</span></div>
          <div style={{marginTop: 22, height: 62, borderRadius: 18, background: frame > 148 ? H.lime : "rgba(255,255,255,.13)", color: frame > 148 ? H.ink : "rgba(255,255,255,.45)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 22, fontWeight: 600}}>构建我的学习路径 →</div>
          <div style={{position: "absolute", left: 42, right: 42, bottom: 42, display: "flex", justifyContent: "space-between", color: "rgba(255,255,255,.38)", fontSize: 17}}><span>State-aware learning</span><span>01 / 05</span></div>
        </Interactive.Div>
        <Interactive.Div name="Generated experience preview" style={{padding: "42px 46px", position: "relative", overflow: "hidden"}}>
          <div style={{display: "flex", justifyContent: "space-between", alignItems: "center"}}><div><div style={{fontSize: 18, color: H.muted, letterSpacing: ".12em"}}>LIVE LEARNING EXPERIENCE</div><div style={{fontSize: 27, marginTop: 9}}>系统正在根据你的状态生成下一步</div></div><div style={{padding: "11px 16px", borderRadius: 99, background: "#EFF0EC", color: H.muted, fontSize: 17}}>LIVE</div></div>
          <div style={{display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 9, marginTop: 32}}>{stages.map((item, index) => <div key={item} style={{height: 48, borderRadius: 14, display: "grid", placeItems: "center", fontSize: 17, background: index === stage ? H.ink : index < stage ? "#E9FFD0" : "#EFF0EC", color: index === stage ? "white" : index < stage ? H.ink : H.muted, borderBottom: index === stage ? `4px solid ${H.lime}` : "4px solid transparent"}}>{item}</div>)}</div>
          <div style={{position: "absolute", left: 46, right: 46, top: 190, bottom: 44, borderRadius: 28, border: `1px solid ${H.line}`, padding: 34, background: "linear-gradient(145deg,#FFFFFF,#F7F8F4)", opacity: interpolate(frame, [154, 180], [0, 1], {extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.bezier(.16, 1, .3, 1)}), translate: interpolate(frame, [154, 180], ["0px 24px", "0px 0px"], {extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.bezier(.16, 1, .3, 1)})}}><ResultPanel stage={stage} frame={frame} /></div>
        </Interactive.Div>
      </div>
    </AbsoluteFill>
  );
};
