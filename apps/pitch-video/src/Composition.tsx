import type {CSSProperties, ReactNode} from "react";
import {
  AbsoluteFill,
  Audio,
  Composition,
  Img,
  Sequence,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

const FPS = 30;
const DURATION = 90 * FPS;
const C = {
  ink: "#09090b",
  paper: "#f7f7f5",
  white: "#ffffff",
  muted: "#a1a1aa",
  line: "rgba(255,255,255,0.14)",
  lime: "#d9ff56",
  lilac: "#b9a7ff",
  cyan: "#73e8ff",
  coral: "#ff8f72",
};
const clamp = {extrapolateLeft: "clamp", extrapolateRight: "clamp"} as const;

export type PitchVideoProps = {guideNarration: boolean};
type Scene = {from: number; duration: number; kicker: string; captions: string[]; voiceDelay?: number};

const SCENES: Scene[] = [
  {from: 0, duration: 240, kicker: "01 · THE DIFFERENCE", voiceDelay: 6, captions: ["同一个问题，为什么答案总是不一样？", "基础、目标、节奏不同。答案，本就不该一样。"]},
  {from: 240, duration: 300, kicker: "02 · INTRODUCING LINGXI", captions: ["这是 LingXi，面向个人学习任务的 AI 学习工作台。", "让 AI 学习真正因你而变。"]},
  {from: 540, duration: 360, kicker: "03 · ONE WORKSPACE", captions: ["从一次学习请求开始，LingXi 持续理解学习目标、历史交互和当前知识状态。", "在一个工作台中，承接完整学习任务。"]},
  {from: 900, duration: 360, kicker: "04 · STATE ENGINE", captions: ["它不依赖预设的固定流程。", "目标、掌握度、误区与新的学习证据，共同决定下一步。"]},
  {from: 1260, duration: 390, kicker: "05 · MULTI-AGENT COLLABORATION", captions: ["多个专业 Agent 以 Skill 为能力单元，按需组合、并行协作。", "完成讲解、知识图解、动态练习与学习反馈。"]},
  {from: 1650, duration: 330, kicker: "06 · THE LEARNING LOOP", captions: ["每一次作答和交互，都会成为新的学习证据。", "持续更新掌握度、发现薄弱点，让教学策略共同成长。"]},
  {from: 1980, duration: 390, kicker: "07 · VALIDATED IN CLASS", captions: ["初版方案已经应用于真实《计算机网络》课程。", "累计服务超过 200 人次，验证完整学习闭环。"]},
  {from: 2370, duration: 330, kicker: "08 · BUILD WHAT'S NEXT", voiceDelay: 6, captions: ["LingXi 将在《优化理论》和《数据库》中深入推行。", "访问官网、预约演示或联系我们，一起构建学习的下一步。"]},
];

const fade = (f: number, d: number) => interpolate(f, [0, 18, d - 18, d], [0, 1, 1, 0], clamp);

const FadeScene = ({duration, children, light = false}: {duration: number; children: ReactNode; light?: boolean}) => {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill style={{background: light ? C.paper : C.ink, color: light ? C.ink : C.white, opacity: fade(f, duration), overflow: "hidden"}}>
      {children}
    </AbsoluteFill>
  );
};

const Grain = ({light = false}: {light?: boolean}) => (
  <AbsoluteFill style={{opacity: light ? 0.06 : 0.1, background: "repeating-linear-gradient(0deg, transparent 0px, transparent 3px, rgba(127,127,127,.14) 4px)", mixBlendMode: light ? "multiply" : "screen", pointerEvents: "none"}} />
);

const Chrome = ({children, style}: {children: ReactNode; style?: CSSProperties}) => (
  <div style={{borderRadius: 24, border: "1px solid rgba(255,255,255,0.16)", background: "rgba(255,255,255,0.07)", boxShadow: "0 40px 120px rgba(0,0,0,0.34)", backdropFilter: "blur(20px)", ...style}}>{children}</div>
);

const SceneMeta = ({text, light = false}: {text: string; light?: boolean}) => (
  <div style={{position: "absolute", top: 66, left: 76, fontSize: 16, letterSpacing: "0.16em", fontWeight: 600, color: light ? "rgba(9,9,11,0.48)" : "rgba(255,255,255,0.48)"}}>{text}</div>
);

const Wordmark = ({light = false, width = 152}: {light?: boolean; width?: number}) => (
  <Img src={staticFile(light ? "brand/wordmark-on-light.svg" : "brand/wordmark-on-dark.svg")} style={{width, height: "auto"}} />
);

const ProblemScene = () => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const enter = spring({frame: f, fps, config: {damping: 18, stiffness: 90}});
  return (
    <FadeScene duration={240}>
      <SceneMeta text={SCENES[0].kicker} />
      <div style={{position: "absolute", inset: "210px 90px auto", textAlign: "center", transform: `translateY(${(1 - enter) * 48}px)`, opacity: enter}}>
        <div style={{fontSize: 88, fontWeight: 500, letterSpacing: "-0.055em", lineHeight: 1}}>同一个问题，</div>
        <div style={{fontSize: 122, fontWeight: 500, letterSpacing: "-0.064em", lineHeight: 1.08, marginTop: 18}}>为什么答案总是<span style={{color: C.lime}}>不一样？</span></div>
        <div style={{display: "flex", gap: 28, marginTop: 88, justifyContent: "center"}}>
          {["基础不同", "目标不同", "节奏不同"].map((word, i) => {
            const p = spring({frame: f - 54 - i * 10, fps, config: {damping: 18}});
            return <div key={word} style={{width: 300, padding: "22px 28px", border: `1px solid ${C.line}`, borderRadius: 999, fontSize: 28, color: C.muted, opacity: p, transform: `translateY(${(1 - p) * 22}px)`, background: "rgba(255,255,255,.035)"}}>{word}</div>;
          })}
        </div>
        <div style={{fontSize: 34, marginTop: 52, color: C.white, opacity: interpolate(f, [102, 132], [0, 1], clamp)}}>答案，本就不该一样。</div>
      </div>
      <div style={{position: "absolute", width: 700, height: 700, right: -220, bottom: -330, borderRadius: "50%", background: `radial-gradient(circle, ${C.lilac}44, transparent 68%)`}} />
      <Grain />
    </FadeScene>
  );
};

const BrandScene = () => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const p = spring({frame: f - 12, fps, config: {damping: 17, stiffness: 84}});
  return (
    <FadeScene duration={300}>
      <SceneMeta text={SCENES[1].kicker} />
      <AbsoluteFill style={{justifyContent: "center", alignItems: "center", zIndex: 2}}>
        <div style={{opacity: p, transform: `scale(${0.92 + p * 0.08})`, textAlign: "center"}}>
          <Wordmark width={300} />
          <div style={{fontSize: 72, letterSpacing: "-0.05em", marginTop: 58, fontWeight: 500}}>AI 学习，<span style={{color: C.lime}}>因你而变。</span></div>
          <div style={{fontSize: 27, color: C.muted, marginTop: 25}}>面向个人学习任务的 AI 学习工作台</div>
        </div>
      </AbsoluteFill>
      <AbsoluteFill style={{inset: -200, background: "radial-gradient(circle at 28% 70%, rgba(115,232,255,.13), transparent 32%), radial-gradient(circle at 72% 28%, rgba(185,167,255,.16), transparent 34%)"}} />
      <Grain />
    </FadeScene>
  );
};

const WorkspaceScene = () => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const enter = spring({frame: f - 18, fps, config: {damping: 19, stiffness: 72}});
  const zoom = interpolate(f, [30, 340], [1, 1.07], clamp);
  return (
    <FadeScene duration={360}>
      <SceneMeta text={SCENES[2].kicker} />
      <div style={{position: "absolute", left: 76, top: 142}}><div style={{fontSize: 66, fontWeight: 500, letterSpacing: "-0.05em"}}>一个工作台，</div><div style={{fontSize: 66, fontWeight: 500, letterSpacing: "-0.05em", color: C.cyan}}>承接完整学习任务。</div></div>
      <div style={{position: "absolute", left: 300, top: 358, width: 1320, height: 650, borderRadius: 24, overflow: "hidden", boxShadow: "0 45px 130px rgba(0,0,0,.5)", opacity: enter, transform: `translateY(${(1 - enter) * 80}px) scale(${zoom})`, transformOrigin: "50% 20%"}}>
        <Img src={staticFile("product/learning-workspace.png")} style={{width: "100%", height: "100%", objectFit: "cover"}} />
        <div style={{position: "absolute", inset: 0, boxShadow: "inset 0 0 0 1px rgba(0,0,0,.12)", borderRadius: 24}} />
      </div>
      <Grain />
    </FadeScene>
  );
};

const StateNode = ({label, x, y, color, delay}: {label: string; x: number; y: number; color: string; delay: number}) => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const p = spring({frame: f - delay, fps, config: {damping: 18}});
  return <div style={{position: "absolute", left: x, top: y, width: 210, height: 98, borderRadius: 22, border: `1px solid ${color}88`, background: `${color}16`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 25, opacity: p, transform: `scale(${0.82 + 0.18 * p})`, boxShadow: `0 0 58px ${color}18`}}>{label}</div>;
};

const StateScene = () => {
  const f = useCurrentFrame();
  const progress = interpolate(f, [52, 290], [0, 1], clamp);
  return (
    <FadeScene duration={360}>
      <SceneMeta text={SCENES[3].kicker} />
      <div style={{position: "absolute", left: 76, top: 155, width: 700}}>
        <div style={{fontSize: 64, fontWeight: 500, letterSpacing: "-0.052em", lineHeight: 1.08}}>不走固定流程。<br /><span style={{color: C.lilac}}>让状态决定下一步。</span></div>
        <div style={{fontSize: 25, lineHeight: 1.55, color: C.muted, marginTop: 32, width: 610}}>系统把目标、掌握度、误区与每次学习证据，组织成可持续更新的学习上下文。</div>
      </div>
      <Chrome style={{position: "absolute", left: 845, top: 120, width: 960, height: 790}}>
        <svg width="960" height="790" style={{position: "absolute", inset: 0}}>
          {[["M 220 190 C 420 190, 330 390, 475 390", C.cyan], ["M 740 190 C 540 190, 630 390, 485 390", C.lilac], ["M 475 485 C 475 565, 260 565, 230 650", C.lime], ["M 485 485 C 485 565, 700 565, 730 650", C.coral]].map(([d, color]) => <path key={d} d={d} fill="none" stroke={color} strokeOpacity=".45" strokeWidth="3" strokeDasharray="10 12" strokeDashoffset={100 * (1 - progress)} />)}
        </svg>
        <StateNode label="学习目标" x={110} y={135} color={C.cyan} delay={18} /><StateNode label="历史证据" x={640} y={135} color={C.lilac} delay={28} /><StateNode label="学习状态" x={375} y={342} color={C.white} delay={55} /><StateNode label="选择 Skill" x={120} y={606} color={C.lime} delay={82} /><StateNode label="动态重规划" x={630} y={606} color={C.coral} delay={92} />
      </Chrome>
      <Grain />
    </FadeScene>
  );
};

type AgentIconKind = "explain" | "visualize" | "practice" | "feedback";

const AgentIcon = ({kind, color}: {kind: AgentIconKind; color: string}) => {
  const paths: Record<AgentIconKind, ReactNode> = {
    explain: <><path d="M9 10h30a6 6 0 0 1 6 6v16a6 6 0 0 1-6 6H24l-10 8v-8H9a6 6 0 0 1-6-6V16a6 6 0 0 1 6-6Z" /><path d="M14 20h20M14 28h14" /></>,
    visualize: <><circle cx="12" cy="15" r="5" /><circle cx="40" cy="15" r="5" /><circle cx="26" cy="39" r="5" /><path d="m16 18 7 16m13-16-7 16M17 15h18" /></>,
    practice: <><path d="M11 8h24l7 7v29H11Z" /><path d="M35 8v9h8M18 27l5 5 11-12M18 39h16" /></>,
    feedback: <><path d="M8 43V10M8 43h38" /><path d="m14 34 9-10 8 5 12-16" /><circle cx="14" cy="34" r="2" /><circle cx="23" cy="24" r="2" /><circle cx="31" cy="29" r="2" /><circle cx="43" cy="13" r="2" /></>,
  };
  return <div style={{width: 58, height: 58, borderRadius: 17, display: "flex", alignItems: "center", justifyContent: "center", color, background: `${color}14`, border: `1px solid ${color}55`, boxShadow: `0 0 42px ${color}22`}}><svg width="39" height="39" viewBox="0 0 52 52" fill="none" stroke="currentColor" strokeWidth="2.3" strokeLinecap="round" strokeLinejoin="round">{paths[kind]}</svg></div>;
};

const AgentCard = ({name, detail, color, delay, icon}: {name: string; detail: string; color: string; delay: number; icon: AgentIconKind}) => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const p = spring({frame: f - delay, fps, config: {damping: 18, stiffness: 105}});
  return <div style={{flex: 1, height: 300, border: "1px solid rgba(255,255,255,.13)", borderRadius: 24, background: "rgba(255,255,255,.055)", padding: 30, opacity: p, transform: `translateY(${(1 - p) * 45}px)`}}><AgentIcon kind={icon} color={color} /><div style={{fontSize: 31, fontWeight: 500, marginTop: 45}}>{name}</div><div style={{fontSize: 20, color: C.muted, marginTop: 12, lineHeight: 1.45}}>{detail}</div></div>;
};

const AgentsScene = () => {
  const f = useCurrentFrame();
  return (
    <FadeScene duration={390}>
      <SceneMeta text={SCENES[4].kicker} />
      <div style={{position: "absolute", left: 76, top: 150}}><div style={{fontSize: 65, fontWeight: 500, letterSpacing: "-0.052em"}}>专业 Agent，各司其职。</div><div style={{fontSize: 26, color: C.muted, marginTop: 22}}>按需组合，并行协作，把复杂学习任务变成可交付成果。</div></div>
      <div style={{position: "absolute", left: 76, right: 76, top: 342, display: "flex", gap: 22}}><AgentCard name="讲解" detail="根据水平调整概念深度与表达路径" color={C.cyan} delay={32} icon="explain" /><AgentCard name="图解" detail="把抽象知识转化为可视化学习体验" color={C.lilac} delay={44} icon="visualize" /><AgentCard name="练习" detail="围绕薄弱点动态生成题型与难度" color={C.lime} delay={56} icon="practice" /><AgentCard name="反馈" detail="从作答证据中识别误区与掌握变化" color={C.coral} delay={68} icon="feedback" /></div>
      <div style={{position: "absolute", left: 76, bottom: 94, fontSize: 20, letterSpacing: "0.09em", color: C.muted, opacity: interpolate(f, [92, 130], [0, 1], clamp)}}>EVERYTHING IS A SKILL</div>
      <Grain />
    </FadeScene>
  );
};

const LoopScene = () => {
  const f = useCurrentFrame();
  const rotation = interpolate(f, [0, 330], [-25, 145], clamp);
  const items = ["Goal", "Plan", "Act", "Observe", "Update State", "Re-plan"];
  return (
    <FadeScene duration={330} light>
      <SceneMeta text={SCENES[5].kicker} light />
      <div style={{position: "absolute", left: 92, top: 218, width: 720}}>
        <div style={{fontSize: 68, fontWeight: 500, letterSpacing: "-0.056em", lineHeight: 1.06}}>每一次学习，<br />都让下一步更准确。</div>
        <div style={{fontSize: 25, color: "rgba(9,9,11,.57)", lineHeight: 1.55, marginTop: 34, width: 610}}>反馈成为新证据，掌握度持续更新，教学策略随学习者共同成长。</div>
        <div style={{display: "flex", gap: 12, marginTop: 52}}>{["证据写入", "状态更新", "策略重规划"].map((label) => <div key={label} style={{padding: "12px 17px", borderRadius: 999, border: "1px solid rgba(9,9,11,.13)", background: C.white, fontSize: 17}}>{label}</div>)}</div>
      </div>
      <div style={{position: "absolute", right: 58, top: 155, width: 940, height: 690, perspective: 1000}}>
        <div style={{position: "absolute", left: 118, top: 198, width: 710, height: 292, borderRadius: "50%", border: "2px solid rgba(9,9,11,.2)", transform: "rotate(-8deg)", boxShadow: "0 55px 90px rgba(9,9,11,.13), inset 0 0 80px rgba(185,167,255,.12)"}} />
        <div style={{position: "absolute", left: 188, top: 236, width: 570, height: 218, borderRadius: "50%", border: "1px solid rgba(9,9,11,.12)", transform: "rotate(-8deg)"}} />
        <div style={{position: "absolute", left: 342, top: 218, width: 270, height: 270, borderRadius: "50%", background: "radial-gradient(circle at 34% 28%, #454549, #09090b 62%)", color: C.white, display: "flex", alignItems: "center", justifyContent: "center", textAlign: "center", fontSize: 29, lineHeight: 1.25, boxShadow: "0 45px 80px rgba(9,9,11,.3), inset -24px -30px 45px rgba(0,0,0,.35), inset 15px 14px 30px rgba(255,255,255,.13)", zIndex: 3}}>个性化<br />学习闭环</div>
        {items.map((item, i) => {
          const a = ((i / items.length) * 360 + rotation) * Math.PI / 180;
          const depth = (Math.sin(a) + 1) / 2;
          const x = 475 + Math.cos(a) * 355;
          const y = 352 + Math.sin(a) * 146;
          return <div key={item} style={{position: "absolute", left: x - 77, top: y - 27, width: 154, padding: "13px 10px", borderRadius: 99, background: i === 4 ? C.ink : "rgba(255,255,255,.94)", color: i === 4 ? C.white : C.ink, border: "1px solid rgba(9,9,11,.14)", textAlign: "center", fontSize: 17, transform: `scale(${0.82 + depth * 0.24})`, boxShadow: `0 ${8 + depth * 20}px ${22 + depth * 30}px rgba(0,0,0,${0.08 + depth * 0.12})`, opacity: 0.64 + depth * 0.36, zIndex: Math.round(2 + depth * 4)}}>{item}</div>;
        })}
      </div>
      <Grain light />
    </FadeScene>
  );
};

const ProofScene = () => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const p = spring({frame: f - 34, fps, config: {damping: 16, stiffness: 88}});
  const count = Math.round(interpolate(p, [0, 1], [0, 200], clamp));
  return (
    <FadeScene duration={390}>
      <SceneMeta text={SCENES[6].kicker} />
      <div style={{position: "absolute", left: 76, top: 145, fontSize: 67, fontWeight: 500, letterSpacing: "-0.052em"}}>从架构，走进真实课堂。</div>
      <div style={{position: "absolute", left: 76, right: 76, top: 340, display: "grid", gridTemplateColumns: "1.05fr 1fr", gap: 25}}>
        <Chrome style={{height: 470, padding: "54px 58px", borderColor: `${C.lime}66`, background: `${C.lime}0d`}}><div style={{fontSize: 21, color: C.muted}}>REAL-WORLD USAGE</div><div style={{fontSize: 142, letterSpacing: "-0.07em", marginTop: 38, lineHeight: 0.9}}>{count}+</div><div style={{fontSize: 31, marginTop: 42}}>累计服务人次</div><div style={{fontSize: 21, color: C.muted, marginTop: 14}}>初版方案已进入真实课程验证</div></Chrome>
        <Chrome style={{height: 470, padding: "54px 58px"}}><div style={{fontSize: 21, color: C.muted}}>FIRST DEPLOYMENT</div><div style={{fontSize: 55, letterSpacing: "-0.04em", marginTop: 64}}>《计算机网络》</div><div style={{height: 1, background: C.line, marginTop: 56}} /><div style={{fontSize: 24, color: C.muted, marginTop: 34, lineHeight: 1.5}}>在真实教学场景中验证学习任务组织、状态更新与多 Agent 协作。</div></Chrome>
      </div>
      <Grain />
    </FadeScene>
  );
};

const ClosingScene = () => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const p = spring({frame: f - 18, fps, config: {damping: 18, stiffness: 78}});
  return (
    <FadeScene duration={330}>
      <SceneMeta text={SCENES[7].kicker} />
      <div style={{position: "absolute", left: 76, right: 76, top: 140, textAlign: "center", opacity: p, transform: `translateY(${(1 - p) * 35}px)`}}>
        <div style={{fontSize: 22, color: C.muted, letterSpacing: ".09em"}}>NEXT IN CLASS</div>
        <div style={{display: "flex", justifyContent: "center", gap: 14, marginTop: 22}}>{["优化理论", "数据库"].map((course) => <div key={course} style={{fontSize: 26, padding: "13px 23px", borderRadius: 999, border: `1px solid ${C.line}`}}>《{course}》</div>)}</div>
        <div style={{fontSize: 68, fontWeight: 500, letterSpacing: "-0.055em", marginTop: 48}}>和我们一起，构建学习的下一步。</div>
        <div style={{display: "grid", gridTemplateColumns: "1fr 1fr 1.15fr", gap: 14, width: 1300, margin: "46px auto 0"}}>
          {[{label: "访问官网", value: "lingxilearn.cn"}, {label: "预约演示 · 联系团队", value: "team@lingxilearn.cn"}, {label: "查看开源项目", value: "github.com/LingXi-Org/LingxiLearn"}].map(({label, value}, i) => <div key={label} style={{padding: "22px 20px", borderRadius: 18, border: `1px solid ${i === 0 ? C.lime + "88" : C.line}`, background: i === 0 ? `${C.lime}0d` : "rgba(255,255,255,.035)", textAlign: "left"}}><div style={{fontSize: 16, color: C.muted, letterSpacing: ".06em"}}>{label}</div><div style={{fontSize: i === 2 ? 20 : 23, marginTop: 11}}>{value}</div></div>)}
        </div>
        <div style={{marginTop: 46, display: "flex", alignItems: "center", justifyContent: "center", gap: 30}}><Wordmark width={132} /><div style={{width: 1, height: 28, background: C.line}} /><div style={{fontSize: 18, color: C.muted, letterSpacing: "0.08em"}}>STATE DECIDES NEXT.</div></div>
      </div>
      <Grain />
    </FadeScene>
  );
};

const Caption = ({scene}: {scene: Scene}) => {
  const f = useCurrentFrame();
  const delay = scene.voiceDelay ?? 18;
  const phraseLength = (scene.duration - delay - 22) / scene.captions.length;
  const index = Math.max(0, Math.min(scene.captions.length - 1, Math.floor((f - delay) / phraseLength)));
  const phraseFrame = f - delay - index * phraseLength;
  const opacity = interpolate(phraseFrame, [0, 7, phraseLength - 7, phraseLength], [0, 1, 1, 0], clamp);
  if (f < delay) return null;
  return <div style={{position: "absolute", left: "50%", bottom: 40, transform: `translateX(-50%) translateY(${(1 - opacity) * 8}px)`, zIndex: 30, maxWidth: 1500, whiteSpace: "nowrap", color: C.white, background: "rgba(9,9,11,.78)", border: "1px solid rgba(255,255,255,.12)", borderRadius: 12, padding: "12px 22px", fontSize: 24, lineHeight: 1.35, letterSpacing: "0.01em", opacity, boxShadow: "0 10px 40px rgba(0,0,0,.22)"}}>{scene.captions[index]}</div>;
};

const PitchVideo: React.FC<PitchVideoProps> = ({guideNarration}) => {
  const components = [ProblemScene, BrandScene, WorkspaceScene, StateScene, AgentsScene, LoopScene, ProofScene, ClosingScene];
  return (
    <AbsoluteFill style={{backgroundColor: C.ink}}>
      {guideNarration ? <Audio src={staticFile("audio/formal/score.wav")} volume={0.48} /> : null}
      {SCENES.map((scene, i) => {
        const Component = components[i];
        const voiceDelay = scene.voiceDelay ?? 18;
        return <Sequence key={scene.kicker} from={scene.from} durationInFrames={scene.duration}><Component />{guideNarration ? <Sequence from={voiceDelay}><Audio src={staticFile(`audio/formal/${String(i + 1).padStart(2, "0")}.wav`)} volume={0.98} /></Sequence> : null}<Caption scene={scene} /></Sequence>;
      })}
    </AbsoluteFill>
  );
};

export const PitchVideoComposition = () => (
  <Composition id="LingXiPitch90" component={PitchVideo} durationInFrames={DURATION} fps={FPS} width={1920} height={1080} defaultProps={{guideNarration: true}} />
);
