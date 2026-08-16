# LingxiHarness：面向有状态自主智能体的 Skill-Native 运行时架构

> **LingxiHarness: A Skill-Native Runtime for Stateful and Constrained Autonomous Agents**

## 摘要

随着大语言模型从单轮生成模型演化为能够调用工具、维护状态并持续与环境交互的自主智能体，Agent 系统的核心问题正在从 Prompt Engineering 转向 Runtime Engineering。ReAct 等工作证明了“推理—行动—观察”循环对于环境交互的重要性，而工业界也逐渐将状态管理、工具执行、Guardrail、Tracing 与 Human-in-the-loop 纳入统一的 Agent Runtime。[1]

本文提出 **LingxiHarness**，一个面向有状态自主任务的 **Skill-Native Agent Harness**。不同于传统 `intent → route → fixed workflow` 范式，LingxiHarness 不在控制流中预定义领域执行路径，而是在每轮执行时依据目标、当前状态和可用能力动态计算下一步动作。

系统围绕三个核心设计展开：

1. **State-Driven Orchestration**：下一步行为由当前状态动态计算，而不是由固定工作流边决定；
2. **Skill-Native Capability Composition**：Agent 的能力由可注册、可组合的 Skill 决定，而不是固化在角色 Prompt 中；
3. **Evidence-Grounded Constrained Autonomy**：执行结果必须形成可验证证据，状态变化与自主行为受到 Runtime Guardrail 约束。

LingxiHarness 最初应用于 LingxiLearn 个性化学习系统。在该场景下，同一个学习请求可以因学习者的掌握程度、误区、前置知识和历史证据不同而产生不同的执行路径，从而使个性化从 Prompt 层面的文本差异提升为 Runtime 层面的行为差异。

**关键词：** Agent Harness；Agent Runtime；Skill-Native；Stateful Agent；Capability Orchestration；Adaptive Learning

---

# 1. 引言

当前大量 Agent 系统仍然建立在固定路由之上：

```text
User Input
    ↓
Intent Classification
    ↓
Route
    ↓
Predefined Agent / Workflow
    ↓
Response
```

这种模式本质上仍是一种 Workflow：开发者预先定义可能出现的路径，模型主要负责决定进入哪一条路径。Anthropic 将 Workflow 与 Agent 区分为两类系统：前者按照预定义代码路径组织模型和工具，而后者允许模型根据任务和环境反馈动态决定后续过程。[2]

固定 Workflow 在流程稳定的场景下具有较高确定性，但随着任务开始具有长期状态、动态反馈和开放能力空间，其拓扑复杂度会迅速增加。

LingxiLearn 原有架构同样采用意图分类、关键词判断和固定条件边完成领域路由；不同教学能力被预先连接为固定执行路径。

LingxiHarness 的出发点因此不是创建更多 Agent，而是重新定义控制权：

> **运行时不提前决定完整工作流，只定义执行边界；具体下一步由当前状态决定。**

这一思想可以抽象为：

\[
A_{t+1}=\pi(G_t,S_t,C_t)
\]

其中：

- \(G_t\) 表示当前目标；
- \(S_t\) 表示当前状态；
- \(C_t\) 表示当前可用能力集合；
- \(A_{t+1}\) 表示下一步实际执行动作。

这与传统：

\[
A_{t+1}=Workflow[A_t]
\]

存在根本差异。

---

# 2. LingxiHarness 总体架构

LingxiHarness 将 Agent Runtime 简化为一个持续循环：

```text
             ┌─────────────────────────────┐
             │                             │
             ↓                             │
Goal → Read State → Plan → Dispatch        │
                            ↓              │
                         Observe           │
                            ↓              │
                         Evidence          │
                            ↓              │
                      Update State         │
                            ↓              │
                      Evaluate Goal        │
                      ↙           ↘        │
                    Done          Replan ──┘
```

其核心控制图仅包含：

```text
interpret_goal
      ↓
orchestrate
      ↓
dispatch
      ↓
observe
      ↓
update_state
      ↓
evaluate_goal
```

控制流中不出现 `QuizAgent`、`VisualAgent`、`TutorAgent` 等领域实体，也不存在“用户要求 X，因此进入 Workflow X”的固定映射。具体领域能力统一在运行时通过 `capability → skill → provider` 解析。

这种架构保留了 Workflow 的确定性生命周期，同时允许领域执行路径在运行过程中动态形成。

---

# 3. State-Driven Orchestration

## 3.1 状态是一等对象

LingxiHarness 的第一个核心设计是：

> **State determines routing.**

LLM Agent 的长期行为依赖于对过去交互和当前环境状态的维护。Generative Agents 等研究已经证明，持续保存 experience 并将其重新用于 planning，是长期一致行为的重要基础。[3]

LingxiHarness 不允许关键状态仅存在于模型 Context Window 中，而是将状态持久化为结构化 Runtime Objects：

```text
State
├── Profile
├── Evidence
├── Goal
├── Plan
├── Budget
└── Capability Registry
```

在 LingxiLearn 中，长期 Profile 进一步细化到：

```text
Learner × Knowledge Point
```

并维护：

```yaml
mastery:
learning_state:
misconceptions:
prerequisites:
evidence_count:
review_due_at:
next_step:
```



因此系统面对相同用户输入时，可以因为状态不同产生不同决策。

形式化表示为：

\[
G_1=G_2,\qquad S_1\neq S_2
\]

允许：

\[
\pi(G_1,S_1)\neq\pi(G_2,S_2)
\]

这构成了运行时个性化的基础。

---

## 3.2 动态候选动作

LingxiHarness 不允许 LLM 直接任意生成下一步动作。

Runtime 首先根据当前状态生成合法 Candidate Set：

\[
C_t=
\{a \mid
Enabled(a)
\land
Precondition(a,S_t)
\land
Permitted(a)
\}
\]

随后才允许模型在该集合中进行语义判断与组合。

当前实现使用：

\[
U(a)=
\frac{ExpectedGain(a)}
{NormalizedCost(a)}
\]

作为基础效用函数。

例如在教育场景中：

```text
前置知识掌握不足
→ prerequisite capability ↑

缺少学习证据
→ assessment capability ↑

存在明确误区
→ targeted explanation ↑

到达复习时间
→ review capability ↑
```



这种方法将确定性约束与 LLM 判断结合起来：

```text
Runtime
    ↓
生成合法动作空间

LLM
    ↓
判断当前最合理动作

Runtime
    ↓
验证并执行
```

因此 LingxiHarness 并非完全开放式自治，而是一种 **bounded planning**。

---

# 4. Skill-Native Capability Composition

LingxiHarness 的第二个核心设计是：

> **能力属于 Skill，而不是 Agent 角色。**

传统多智能体系统通常将不同能力绑定到不同角色。例如 AutoGen 通过多个具有不同配置和职责的 Agent 进行会话协作。[4]

这种模式可以表达复杂角色关系，但当系统能力不断增长时，容易形成：

```text
Agent
├── Role Prompt
├── Tools
├── Policies
├── Workflow
└── Capability
```

之间的紧耦合。

LingxiHarness 将这一结构拆分为：

```text
Capability
    ↓
Skill
    ↓
Provider
```

Planner 只处理抽象 Capability，例如：

```text
teach.explain
content.visual
assess.generate
assess.grade
graph.prerequisite
review.schedule
```

而不会直接规划：

```text
QuizAgent
VisualAgent
TutorAgent
```

---

## 4.1 Skill 作为 Capability Contract

每个 Skill 在 Registry 中具有机器可读元信息：

```yaml
skill_id:
capabilities:
input_schema:
output_schema:
preconditions:
cost:
provider:
version:
enabled:
```



因此 Skill 不只是 Prompt Fragment，而成为一个：

> **Executable Capability Contract**

Anthropic 的 Agent Skills 同样采用可组合能力的思想，将 instructions、scripts 和 resources 封装为可按需发现和加载的能力包。[5]

LingxiHarness 在此基础上进一步将前置条件、成本、Provider 和启用状态纳入 Runtime，从而允许 Orchestrator 自动发现和选择 Skill。

---

## 4.2 Agent 从角色实体变成能力视图

不同 Agent 不再依赖独立硬编码 System Prompt 定义能力。

可以近似表示为：

\[
Agent=
SkillComposition
+
ExecutionContext
+
PolicyScope
\]

例如：

```text
Tutor
├── teach.explain
├── content.visual
└── dialog.answer

Examiner
├── assess.generate
├── assess.grade
└── evidence.emit
```

二者可以共享相同 Skill，而无需复制实现。

原有 Agent 也因此被重新定位为统一接口的 Provider，领域路由职责则移交给 Harness。

这使系统从：

> **Agent-oriented architecture**

逐渐转向：

> **Capability-oriented runtime**

---

# 5. Evidence-Grounded Constrained Autonomy

LingxiHarness 的第三个核心设计解决两个问题：

1. Agent 如何证明执行真的产生了效果；
2. Agent 的自主范围由谁决定。

---

## 5.1 Evidence-first State Update

LingxiHarness 定义一个关键不变量：

\[
\Delta State \Rightarrow Evidence\neq\varnothing
\]

Agent 不能直接宣告：

```text
“用户已经掌握该知识点。”
```

而必须产生结构化 Evidence，例如：

```text
correct
incorrect
hint_used
error_pattern
self_report
artifact_viewed
```

然后经过：

```text
Observation
    ↓
Evidence
    ↓
State Updater
    ↓
Profile
```

完成状态更新。

这种设计使 Agent 的“判断”与系统保存的“事实”之间存在明确边界。

---

## 5.2 执行完成不等于目标完成

传统 Agent 系统容易将：

```text
Tool returned successfully
```

等同于：

```text
Task completed
```

LingxiHarness 则为每一个 Planned Task 定义声明式完成条件：

```text
artifact_exists
artifact_valid
evidence_observed
profile_reaches
quiz_graded
user_replied
```

因此：

\[
ExecutionSuccess
\not\Rightarrow
TaskSuccess
\]

而是：

\[
TaskSuccess=
ExecutionSuccess
\land
DoneCondition(S_{t+1})
\]

如果 Provider 成功运行，但 `DoneCondition` 不成立，则 Runtime 自动重新规划。

这一设计使系统优化目标从：

> “Agent 是否执行完成”

转向：

> **“目标是否真正达成”。**

Reflexion 所展示的反馈驱动反复尝试同样说明，一次执行失败或结果不足不应自然终止 Agent trajectory。[6]

---

## 5.3 Runtime Guardrail

LingxiHarness 不将安全与可靠性写入 Prompt，而是实现为 Runtime Constraint：

```text
max_steps
max_replans
token_budget
wall_time
allowed_capabilities
permission
user_confirmation
```

对于不可逆行为：

```text
workspace mutation
schedule mutation
skill activation
knowledge graph mutation
```

Runtime 必须进入 Human-in-the-loop 状态后才能继续执行。

因此 Agent 的自主能力可表示为：

\[
Autonomy
\subseteq
Capability
\cap Permission
\cap Budget
\cap Policy
\]

OpenAI Agents SDK 同样将 Guardrails、Human-in-the-loop、Sessions 与 Tracing 作为 Agent Runtime 的独立组成部分，而不是完全依赖模型 Prompt。[7]

LingxiHarness 因而追求的不是 unrestricted autonomy，而是：

> **Constrained Autonomy**

---

# 6. 可观测的 Replanning

如果 Runtime 会动态改变执行路径，那么仅记录最终输出是不够的。

LingxiHarness 为每次决策保存：

```text
goal
candidates
selected
rationale
evidence
profile_before
profile_after
replan_of
```



从而可以重建：

```text
State Before
     ↓
Candidate Set
     ↓
Selected Action
     ↓
Execution
     ↓
Evidence
     ↓
State After
     ↓
Replan?
```

这里的 Trace 不只是模型调用日志，而是 **decision trace**。

系统因此能够回答：

> 为什么选择这个 Skill？

> 为什么没有选择另一个 Skill？

> 这个动作产生了什么证据？

> 什么状态变化导致了下一次 Replan？

这种可追踪性对于非确定 Agent 尤其重要，因为 Agent 系统评价正在从单纯输出正确性逐渐扩展到 interaction trajectory 与最终环境状态。[8]

---

# 7. LingxiLearn：个性化作为 Runtime 行为

LingxiHarness 的首个主要应用是 LingxiLearn。

传统“个性化 AI”通常表现为：

```text
User Profile
     ↓
Prompt Personalization
     ↓
Same Workflow
```

LingxiHarness 则使 Profile 直接进入 Orchestrator：

```text
Goal
 +
Learner State
 +
Evidence
 +
Knowledge Dependencies
      ↓
Capability Planning
      ↓
Dynamic Learning Path
```

例如两个学生都提出：

> “帮我理解傅里叶变换。”

学生 A：

```yaml
prerequisite_mastery: high
evidence_count: low
```

可能获得：

```text
visual explanation
        ↓
retrieval practice
```

学生 B：

```yaml
prerequisite_mastery: low
misconceptions:
  - complex_number
```

可能获得：

```text
prerequisite explanation
        ↓
formative assessment
        ↓
visual explanation
```

因此：

\[
LearningPath_t=
\pi(
Goal,
LearnerState_t,
Evidence_t,
CapabilitySpace
)
\]

并随着学习证据改变：

\[
State_{t+1}\neq State_t
\]

下一步路径也可以发生变化。

这使“个性化”不再只是生成不同措辞，而成为：

> **不同学生实际执行不同的教学过程。**

---

# 8. 设计定位

LingxiHarness 并不试图替代传统 Workflow。

如果任务具有：

```text
步骤稳定
顺序确定
状态变化不会影响路径
```

则固定 DAG 往往更加简单、便宜且可靠。

Anthropic 同样建议优先选择满足任务要求的最简单架构，并仅在路径无法提前确定时使用更高自主性的 Agent。[2]

LingxiHarness 主要针对：

> **目标能够定义，但到达目标的具体路径需要根据执行反馈动态决定的任务。**

即当：

\[
P(A_{t+1}\mid O_t)
\neq
P(A_{t+1})
\]

新的 Observation 会显著影响下一步动作时，State-Driven Runtime 才具有明显价值。

因此 LingxiHarness 所处的位置并非：

```text
Workflow ───────────────── Agent
```

两极中的任意一端，而是：

```text
Deterministic Boundaries
          +
Dynamic Decisions
          +
Observable Feedback
```

---

# 9. 结论

LingxiHarness 提出一种面向有状态自主任务的 Skill-Native Agent Runtime。

其核心结构由三个设计组成：

### 1. State-Driven Orchestration

下一步动作根据：

\[
Goal + State + CapabilitySpace
\]

动态计算，而不是由固定 Workflow Edge 决定。

### 2. Skill-Native Capability Composition

Agent 不再是能力的唯一封装边界。

系统采用：

```text
Capability → Skill → Provider
```

实现可组合、可发现的能力体系。

### 3. Evidence-Grounded Constrained Autonomy

Agent 行为通过 Evidence 改变状态，通过 Done Condition 判断目标是否完成，并通过 Runtime Guardrail 限制自主范围。

最终，LingxiHarness 将传统：

```text
Intent
→ Route
→ Fixed Workflow
→ Response
```

转化为：

```text
Goal
→ State
→ Capabilities
→ Plan
→ Execute
→ Evidence
→ State Update
→ Evaluate
→ Replan
```

其设计哲学可以概括为：

> **The workflow is no longer predefined.  
> The boundaries are.**

---

# References

[1] Yao, S., Zhao, J., Yu, D., et al. **ReAct: Synergizing Reasoning and Acting in Language Models.** ICLR 2023.

[2] Anthropic. **Building Effective Agents.** Anthropic Engineering, 2024.

[3] Park, J. S., O'Brien, J., Cai, C. J., et al. **Generative Agents: Interactive Simulacra of Human Behavior.** UIST 2023.

[4] Wu, Q., Bansal, G., Zhang, J., et al. **AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversation.** COLM 2024.

[5] Anthropic. **Equipping Agents for the Real World with Agent Skills.** Anthropic Engineering, 2025.

[6] Shinn, N., Cassano, F., Gopinath, A., et al. **Reflexion: Language Agents with Verbal Reinforcement Learning.** NeurIPS 2023.

[7] OpenAI. **OpenAI Agents SDK Documentation.** OpenAI, 2025–2026.

[8] Yao, S., Shinn, N., Razavi, P., Narasimhan, K. **τ-bench: A Benchmark for Tool-Agent-User Interaction in Real-World Domains.** 2024.