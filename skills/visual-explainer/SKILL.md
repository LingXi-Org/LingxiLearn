---
name: visual-explainer
description: Create a self-contained, offline interactive HTML explainer for a concept. Use when a user asks to visualize an algorithm, mathematical idea, physical mechanism, system, protocol, or other topic that is easier to understand by seeing and manipulating it. The output is a single zero-dependency HTML file with hand-authored SVG or Canvas, one to three meaningful controls, light/dark support, and an explanation embedded in the visual result. Do not use for text-only answers, static reports, slides, or ordinary charts without an explanatory interaction.
license: MIT
metadata:
  author: LingXi-Org
---

# Visual Explainer

**这个技能只服务一种角色**：接收主智能体派发的知识点，产出一个能独立打开、能动手操作的讲解页面。你是画图的人，不是答题的人——结论要长在图里，不要长在段落里。

产物永远是**一个 `.html` 文件**：零外部请求、双击即开、断网可用、亮暗自适应、可打印。

## 一、先读需求，缺什么就按默认值补

主智能体通常会给：知识点 + 受众 + 想强调的那一点。缺项按下表补齐，**不要反问**，把补的假设写进交付说明。

| 字段 | 缺省时怎么办 |
|---|---|
| 知识点 | 必须有。真的没有就返回「需求不完整」，不要猜 |
| 学习目标 | 自己写一句「操作完之后，学习者应该明白 ___」，这句话是整页的锚 |
| 受众深度 | 默认「懂相邻领域、但没学过这个知识点」 |
| 界面语言 | 默认中文；公式、变量名、代码标识符保持原文 |
| 视觉风格 | 默认学术论文风（衬线标题 + 米白纸面 + 克制配色） |
| 交互形态 | 按 `references/interaction-patterns.md` 的九种模式选一种主模式 |
| 篇幅 | 默认一屏半到三屏：1 个主交互 + 1–2 张辅助图 |
| 外部依赖 | 默认零依赖。只有当需求明确涉及复杂公式排版或高密度统计图，才考虑引 CDN，且必须写降级路径 |

## 二、七步流程，顺序不能换

**颜色排在第六步。** 大部分难看的页面都是从选颜色开始做的。

1. **写死学习目标。** 一句话，写在最前面。后面每加一个元素都要能回答「它服务这句话的哪个词」。
2. **拆出那个会变的量。** 学习者能控制的维度只留 1–3 个。找不出会变的量，说明这个知识点不需要交互，做静态图 + 文字即可。
3. **选形式。** 先定教学形式（九种交互模式之一），再定图表形式（`references/svg-craft.md` 第五节）。**有时答案不是图表**——单一结论就是一个大数字。
4. **排版算坐标。** 680 宽的 viewBox，边距常量 `L=60 R=640 T=40 B=300`，文字宽度按中文 14px/字预算，排完验算不重叠、不出界。
5. **搭骨架。** 从 `assets/template.html` 起手，整段内联 `assets/lingxi.css`，改结构不改令牌。
6. **配色按职责分配。** 身份用 `--c1..--c7` 定序取，量级用单色相深浅，极性用双色相 + 灰中点，状态用保留色。**改了任何颜色就重跑校验器**：
   ```
   node scripts/validate_palette.js "<hex,hex,…>" --mode light
   node scripts/validate_palette.js "<hex,hex,…>" --mode dark
   ```
   FAIL 必须改到 PASS 再往下走。不要靠眼睛判断色盲安全性——这件事是可计算的，就去算。
7. **体检 + 渲染 + 亲眼看。**
   ```
   node scripts/check_page.js <你的页面>.html
   ```
   FAIL 全清、WARN 要么修要么在交付说明里解释。**体检器看不见 JS 运行时生成的 DOM**，所以必须再渲染截图，亮色暗色各看一遍：标签有没有撞、图形有没有溢出、暗色下有没有文字消失。

最后对照 `references/anti-patterns.md` 通读一遍。命中任何一条就是错的。

## 三、不可妥协的十一条

1. **单文件、零依赖、可离线。** 默认不许任何外部请求。确需 CDN 只能用 `cdnjs.cloudflare.com` / `cdn.jsdelivr.net` / `unpkg.com` / `esm.sh`，并且必须有断网降级。
2. **首帧就要教会一件事。** 不许「必须先拖滑块才看得懂」。
3. **控件放在它所控制的图形的下方。** 紧贴那张图，一图一组；不要在页顶做一个管多张图的总控制条。图注夹在图与控件之间，结果数值排在控件之下。
4. **一次 `render()` 全量更新。** 图形、数值、标注、`aria-live` 结论句同步刷新。状态变了而结论文字停在旧值，比没有结论更糟。
5. **所有显示的数字过取整。** `toFixed` / `Math.round` / `Intl.NumberFormat`，滑块设 `step`。
6. **绝不双纵轴。** 拆图或归一化。
7. **颜色跟实体走，不跟排名走。** 分类色定序取用，绝不循环；一张图最多 3 色。
8. **每个 SVG `<text>` 必须带 `t`/`ts`/`th`/`tn` 类。** 漏了在暗色下就是黑字。
9. **暗色模式是选出来的，不是反相出来的。** 每一档单独选、单独跑校验。
10. **只用 400 / 500 两档字重；发丝线 0.5px；无渐变无阴影；句子式大小写；不用 emoji。**
11. **交付前必须渲染截图亲眼看过。** 校验器管颜色，体检器管结构，版面只有眼睛能管。

## 四、交回给主智能体的东西

正文写给人看的部分要短。返回这几项，**不要把整个 HTML 贴回对话**：

```
文件：<绝对路径>
知识点：<一句话>
学习目标：操作完之后，学习者应该明白 ___
主交互：<九种模式里的哪一种> + <控件是什么，改变了什么>
图形清单：图1 <画的是什么> / 图2 <画的是什么>
校验：validate_palette <light PASS / dark PASS>；check_page <n 项 FAIL / m 项 WARN>
截图核对：亮色 ✓ 暗色 ✓
补的假设：<需求里没给、你自己定的那些>
已知取舍：<砍了什么、为什么>
```

**砍了内容就要说。** 因篇幅或复杂度预算删掉的东西必须写进「已知取舍」——不写，读者会以为覆盖是完整的。

## 五、随附文件

| 文件 | 什么时候读 |
|---|---|
| `assets/template.html` | **每次动手前**。可运行的完整骨架（梯度下降学习率示例），已内联全部样式，直接改 |
| `assets/lingxi.css` | 需要查令牌名、或往页面里整段内联时 |
| `references/design-tokens.md` | 配色、字体、间距、彩色底上的文字、已验证的色序与已知失败边界 |
| `references/svg-craft.md` | 算坐标、排文字、画箭头、手写图表、复杂度预算 |
| `references/interaction-patterns.md` | 选交互模式、控件规格、状态同步、可访问性 |
| `references/anti-patterns.md` | **交付前逐条对照**，45 条 |
| `scripts/validate_palette.js` | 改了任何颜色就跑。无依赖，`node` 直接执行 |
| `scripts/check_page.js` | 页面写完就跑。20 项静态检查，FAIL 退出码 1 |
