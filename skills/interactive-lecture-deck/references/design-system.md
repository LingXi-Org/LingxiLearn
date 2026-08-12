# Anthropic 学术 PPT 设计系统

本设计系统将 `interactive-visual-explainer` 的学术论文风约束迁移到固定 16:9 PPT：
**米白纸面、衬线标题、无衬线正文、等宽数字、平面、发丝线、克制分类色、图形主导。**
它不是网页仪表盘，也不是“卡片堆叠”。

## 1. 画布与栅格

| 项 | 值 |
|---|---|
| 画布 | `1280 × 720` px |
| 安全边距 | `64px` |
| 内容区 | `1152 × 592` |
| 栅格 | 12 列；列宽 74；槽宽 24 |
| 基线 | 8px |

`col(n) = 64 + (n-1)×98`；`span(k)=98k-24`。

页面首先像 PPT：大尺度、少元素、清晰视觉中心。不要因为 HTML 能放很多东西就把页面做成网页。

## 2. 字体与字号

字体仅使用系统栈：

```css
--font-serif:"Songti SC","Source Han Serif SC","Noto Serif SC","SimSun",Georgia,"Times New Roman",serif;
--font-sans:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei","Source Han Sans SC","Noto Sans SC","Segoe UI",Roboto,sans-serif;
--font-mono:ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,"Liberation Mono",monospace;
```

只允许 **400 / 500** 两档字重。

| 角色 | 字号 | 字重 | 说明 |
|---|---:|---:|---|
| display | 58 | 500 | opening 主标题 |
| title | 38 | 500 | 内容页“结论型标题” |
| subtitle | 24 | 500 | 图内小标题 / 关键对象 |
| lead | 22 | 400 | 一句话解释 / closing 收束 |
| body | 20 | 400 | 必要正文 |
| annotation | 15–16 | 400 | 图注、标签、来源 |
| data | 24–42 | 500 | 关键数值 / 公式变量，等宽 |

禁止 600/700。强调依靠尺寸、空间、颜色，而不是粗黑。

## 3. 核心颜色令牌

默认只允许 `data-style="anthropic-academic"`。

```css
--paper:#fbfaf7;
--surface:#ffffff;
--sunken:#f4f2ec;
--ink-1:#23231f;
--ink-2:#5f5e5a;
--ink-3:#8a8880;
--rule:rgba(35,35,31,.14);
--rule-strong:rgba(35,35,31,.30);
--accent:#534ab7;

--c1:#7f77dd; --c1-fill:#eeedfe; --c1-ink:#3c3489;
--c2:#1d9e75; --c2-fill:#e1f5ee; --c2-ink:#085041;
--c3:#d85a30; --c3-fill:#faece7; --c3-ink:#712b13;
--c4:#378add; --c4-fill:#e6f1fb; --c4-ink:#0c447c;
--c5:#ba7517; --c5-fill:#faeeda; --c5-ink:#633806;
--c6:#d4537e; --c6-fill:#fbeaf0; --c6-ink:#72243e;
--c7:#639922; --c7-fill:#eaf3de; --c7-ink:#27500a;
--c0:#888780; --c0-fill:#f1efe8; --c0-ink:#444441;
--c-warn:#e24b4a; --c-warn-fill:#fcebeb; --c-warn-ink:#791f1f;
```

分类色按 `c1→c7` 固定顺序取，**单页最多 3 个有语义的彩色身份**。灰色只做结构，不占分类槽位。
状态色（成功/警告/错误）不能拿来做普通系列色。

## 4. 平面学术风硬规则

1. 无渐变、无阴影、无发光、无玻璃拟态、无 blur。
2. 分隔线与框线默认 `0.5px`；选中态最多 `2px`。
3. 圆角仅 `4 / 8 / 12px`；单边强调线不得圆角。
4. 标题使用衬线；正文无衬线；变化数值/公式编号等宽。
5. 不用 emoji；需要图标就画简洁 SVG。
6. 不做 3D 图表。**runtime 的 3D 只用于镜头透视，不参与数据编码。**

## 5. 单页信息密度硬上限

对 `content` 页：

- 顶层内容块建议 ≤ 8，严格上限 10；
- 可见正文总量目标 ≤ 100 个“汉字/ASCII 词”等价单位；超过 140 视为设计失败；
- bullet 最多 3 条，每条最好 ≤ 18 个汉字；
- 连续 prose 块最多 2 个；
- 每页必须有 ≥1 个 `data-visual`；
- 主视觉建议占内容区面积 ≥ 35%，理想为 50–70%；
- 页面标题建议 ≤ 18 个汉字，且必须表达判断、因果或问题，不写空泛章节名。

opening / closing 可以更稀疏，但同样要有视觉中心。

## 6. 图形规则

所有主视觉放在 `data-visual="..."` 元素里，类型建议：

`diagram | chart | process | timeline | comparison | formula | geometry | system | table | image | concept-map`

SVG：

- 图内文字必须使用 `.t / .ts / .th / .tn`；
- 结构线 0.5–1px，数据线 2px 左右；
- 标签尽量就地标注，不靠远端大图例；
- 一张图最多 3 个分类色；
- 只标关键点、极值、转折与被讲解对象，不把每个数据点都写数字。

## 7. 为 zoom 设计

1. 锚点建议最小 `180×72`；更小通常说明目标切得过碎。
2. 相邻锚点间隔 ≥24px；距画布边缘 ≥40px。
3. 一个锚点应覆盖一个**完整可解释对象**：一段曲线 + 标签、一组公式结构、一条流程链，而不是一个孤立字符。
4. 被放大的局部必须单独成立：标签、线条、颜色不能依赖全页上下文才能看懂。
