"use client";

import { GitBranch, ListTodo } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { SimButton } from "@/components/sim/source/button";
import { SimResourceTab } from "@/components/sim/source/resource-tab";
import { SimAgentGraph } from "@/components/sim/sim-agent-graph";
import { SimTaskList } from "@/components/sim/sim-task-list";
import { useAgentArtifact } from "@/hooks/use-agent-artifact";
import { api } from "@/lib/api";
import { agentTaskToAgentRuns, agentTaskToCanvasGraph } from "@/lib/sim-adapter";
import type { AgentTaskEvent, AgentTaskSnapshot, PublicQuizQuestion } from "@/lib/types";

export type ResourceTab = "canvas" | "task-list" | "lesson-intro" | "lecture-deck" | "quiz" | "visual";

export function SimResourcePanel({ task, events, initialTab = "canvas", onBackToConversation }: { task: AgentTaskSnapshot | null; events: AgentTaskEvent[]; initialTab?: ResourceTab; onBackToConversation?: () => void }) {
  const [tab, setTab] = useState<ResourceTab>(initialTab);
  useEffect(() => setTab(initialTab), [initialTab]);
  const graph = agentTaskToCanvasGraph(task, events);
  const runs = task ? agentTaskToAgentRuns(task, events) : [];
  const hasDeck = Boolean(task?.artifacts.lecture_deck.available);
  const hasLessonIntro = Boolean(task?.artifacts.lesson_intro.available);
  const hasQuiz = Boolean(task?.artifacts.quiz.available && task.artifacts.quiz.data);
  const hasVisual = Boolean(task?.artifacts.visual.available);

  useEffect(() => {
    if (tab === "lecture-deck" && !hasDeck) setTab("canvas");
    if (tab === "lesson-intro" && !hasLessonIntro) setTab("canvas");
    if (tab === "quiz" && !hasQuiz) setTab("canvas");
    if (tab === "visual" && !hasVisual) setTab("canvas");
  }, [hasDeck, hasLessonIntro, hasQuiz, hasVisual, tab]);

  if (!task) return <section className="flex h-full min-h-0 items-center justify-center bg-[var(--surface-2)]" data-testid="sim-resource-panel"><div className="text-center text-xs text-[var(--text-muted)]"><GitBranch className="mx-auto mb-3 size-5 opacity-40" /><p>工作区将在提交问题后动态加载</p></div></section>;

  return <section className="flex h-full min-h-0 flex-col bg-[var(--surface-2)]" data-testid="sim-resource-panel">
    <header className="flex min-h-10 shrink-0 items-center gap-2 overflow-x-auto border-b border-[var(--border)] bg-[var(--surface-1)] px-3">
      <span className="grid size-6 shrink-0 place-items-center rounded-md bg-[var(--surface-4)] text-[var(--text-icon)]"><GitBranch className="size-3.5" /></span>
      <span className="shrink-0 text-xs font-medium">工作区</span>
      <nav className="ml-2 flex h-10 items-center gap-1" aria-label="知识点子图工作区页面">
        <SimResourceTab active={tab === "canvas"} onClick={() => setTab("canvas")} icon={<GitBranch className="size-3" />}>Canvas</SimResourceTab>
        <SimResourceTab active={tab === "task-list"} onClick={() => setTab("task-list")} icon={<ListTodo className="size-3" />}>任务列表</SimResourceTab>
        {hasLessonIntro && <SimResourceTab active={tab === "lesson-intro"} onClick={() => setTab("lesson-intro")}>课程引入</SimResourceTab>}
        {hasDeck && <SimResourceTab active={tab === "lecture-deck"} onClick={() => setTab("lecture-deck")}>交互式讲解课件</SimResourceTab>}
        {hasQuiz && <SimResourceTab active={tab === "quiz"} onClick={() => setTab("quiz")}>知识点检测</SimResourceTab>}
        {hasVisual && <SimResourceTab active={tab === "visual"} onClick={() => setTab("visual")}>可视化讲解</SimResourceTab>}
      </nav>
      {onBackToConversation && <SimButton type="button" variant="quiet" size="sm" className="ml-auto shrink-0 lg:hidden" onClick={onBackToConversation}>返回对话</SimButton>}
    </header>
    <div className="min-h-0 flex-1 overflow-auto p-4 sm:p-5">
      {tab === "canvas" && <SimAgentGraph graph={graph} runs={runs} running={task.status === "queued" || task.status === "running"} />}
      {tab === "task-list" && <SimTaskList task={task} events={events} graph={graph} />}
      {tab === "lesson-intro" && <LessonIntroArtifact task={task} />}
      {tab === "lecture-deck" && <LectureDeckArtifact task={task} />}
      {tab === "quiz" && <QuizArtifact task={task} />}
      {tab === "visual" && <VisualArtifact task={task} />}
    </div>
  </section>;
}

function LessonIntroArtifact({ task }: { task: AgentTaskSnapshot }) {
  const artifact = useAgentArtifact(task.id, "lesson-intro", task.artifacts.lesson_intro.available);
  if (artifact.loading) return <div className="p-6 text-xs text-[var(--text-muted)]">正在打开课程引入…</div>;
  if (artifact.error) return <div className="p-6 text-xs text-red-700">课程引入加载失败：{artifact.error}</div>;
  return artifact.content ? <iframe title="课程引入" src={artifact.content} sandbox="allow-scripts" className="h-full min-h-[520px] w-full border-0 bg-white" /> : null;
}

function LectureDeckArtifact({ task }: { task: AgentTaskSnapshot }) {
  const artifact = useAgentArtifact(task.id, "lecture-deck", task.artifacts.lecture_deck.available);
  if (artifact.loading) return <div className="p-6 text-xs text-[var(--text-muted)]">正在打开课件…</div>;
  if (artifact.error) return <div className="p-6 text-xs text-red-700">课件加载失败：{artifact.error}</div>;
  return artifact.content ? <iframe title="交互式讲解课件" src={artifact.content} sandbox="allow-scripts" className="h-full min-h-[520px] w-full border-0 bg-white" /> : null;
}

function VisualArtifact({ task }: { task: AgentTaskSnapshot }) {
  const artifact = useAgentArtifact(task.id, "visual", task.artifacts.visual.available);
  if (artifact.loading) return <div className="p-6 text-xs text-[var(--text-muted)]">正在打开可视化讲解…</div>;
  if (artifact.error) return <div className="p-6 text-xs text-red-700">可视化讲解加载失败：{artifact.error}</div>;
  return artifact.content ? <iframe title="交互式可视化讲解" src={artifact.content} sandbox="allow-scripts" className="h-full min-h-[520px] w-full border-0 bg-white" /> : null;
}

function QuizArtifact({ task }: { task: AgentTaskSnapshot }) {
  const quiz = task.artifacts.quiz.data;
  const [answers, setAnswers] = useState<Record<string, unknown>>({});
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string>();
  const submitted = Boolean(task.quiz_submission);
  const questions = quiz?.questions || [];
  const submissionId = useMemo(() => `sub-${task.id}-${Math.random().toString(36).slice(2, 10)}`, [task.id]);
  if (!quiz) return <div className="p-6 text-xs text-[var(--text-muted)]">题目尚未就绪。</div>;
  const submit = async () => {
    if (submitted || sending) return;
    setSending(true); setError(undefined);
    try { await api.submitAgentQuiz(task.id, submissionId, answers); } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)); } finally { setSending(false); }
  };
  return <div className="quiz-workspace mx-auto max-w-3xl space-y-5">
    <div className="quiz-intro"><p className="quiz-kicker">一次性知识检查</p><h1 className="quiz-title">{quiz.title}</h1><p className="quiz-instructions">{quiz.instructions}</p></div>
    {questions.map((question) => <Question key={question.id} question={question} value={answers[question.id]} disabled={submitted} onChange={(value) => setAnswers((current) => ({ ...current, [question.id]: value }))} />)}
    {error && <p className="text-xs text-red-700">提交失败：{error}</p>}
    {submitted ? <div className="quiz-submitted" role="status">已提交。本套题不能再次作答，正在返回主图。</div> : <button className="quiz-submit" type="button" disabled={sending} onClick={() => void submit()}>{sending ? "提交中…" : "提交全部答案"}</button>}
  </div>;
}

function Question({ question, value, disabled, onChange }: { question: PublicQuizQuestion; value: unknown; disabled: boolean; onChange: (value: unknown) => void }) {
  return <fieldset className="quiz-question" disabled={disabled}><legend className="quiz-question-title">{question.prompt} <span>（{question.points} 分）</span></legend>
    {question.type === "short_text" ? <input className="quiz-text-input" value={typeof value === "string" ? value : ""} onChange={(event) => onChange(event.target.value)} placeholder="输入你的回答" /> : <div className="quiz-options">{question.options.map((option) => <label key={option.id} className="quiz-option"><input type={question.type === "multi_choice" ? "checkbox" : "radio"} name={question.id} checked={question.type === "multi_choice" ? Array.isArray(value) && value.includes(option.id) : value === option.id} onChange={(event) => { if (question.type === "multi_choice") { const current = Array.isArray(value) ? value.map(String) : []; onChange(event.target.checked ? [...current, option.id] : current.filter((item) => item !== option.id)); } else onChange(option.id); }} /><span>{option.label}</span></label>)}</div>}
  </fieldset>;
}
