# 结构化讲解数据 `lecture.json` v2

Schema：`references/lecture.schema.json`；`schemaVersion` 固定为 `zoom-lecture/v2`。

## 1. 顶层

```json
{
  "schemaVersion":"zoom-lecture/v2",
  "deck":{},
  "defaults":{},
  "slides":[]
}
```

`deck.style` 固定为 `anthropic-academic`；画布固定 1280×720。

### v2 最小 step/anchor 形状

生成时直接套用下面的形状，避免混入旧版字段：

```json
{
  "anchors": [{"id":"a-main","label":"主关系","rect":{"x":64,"y":208,"w":720,"h":320}}],
  "steps": [
    {"id":"s02-01","order":1,"kind":"overview","camera":{"mode":"fit"},"advance":"manual"},
    {"id":"s02-02","order":2,"kind":"zoom","camera":{"mode":"anchor","anchorId":"a-main"},"panel":{"placement":"auto","title":"局部关系","body":"……"},"advance":"manual"}
  ]
}
```

`label`、`advance` 和 overview 的 `camera.mode` 都是硬性 schema 字段。overview 不得携带
`anchorId`、`depth`、`scale`、`focus`；SVG 中每个 `<text>` 也必须带 `t`、`ts`、`th` 或 `tn`
类名。

## 2. slides[]

每页新增必填 `role`：

```json
{
  "id":"s02",
  "index":2,
  "role":"content",
  "file":"slides/s02.html",
  "title":"排队一旦持续，时延会迅速放大",
  "anchors":[],
  "steps":[]
}
```

规则：第一张 `opening`，最后一张 `closing`，中间全部 `content`。

## 3. step 节奏

- `opening`：只需要 1 个 `overview`；panel 可省略。
- `content`：必须有 overview，并有 2–4 个 zoom。
- `closing`：以 overview 为主，可有 0–2 个 zoom。

相邻 zoom 默认连续平移，不回全景。

## 4. 教授式 panel 写作

`panel.body` 不是讲义、不是字幕，也不是“把页面换一种说法”。它应像一位熟悉课堂节奏、态度温和的教授，在学生已经看着图的前提下补上关键直觉。

### 推荐长度

**45–140 个汉字/ASCII 词等价单位**。2–4 个短句最自然。

### 推荐结构

优先使用：

1. **观察**：先把学生注意力放到正在放大的那一处。
2. **原因**：解释为什么会这样，或怎样从前一个对象推到这里。
3. **意义**：告诉学生这个观察以后能帮他判断什么。

例如：

> 先盯住这条斜率变陡的线。它不是“链路突然变慢”，而是到达速率开始长期高于服务速率，队列只能越积越长。以后看到时延突然抬头，先问自己：是不是排队从短暂波动变成了持续积累？

### 口吻要求

- 温和、专业、自然，不卖弄。
- 可以用“先看这里”“你可以把它理解成…”“这里真正要抓住的是…”这类课堂口语。
- 允许一个简短反问帮助思考，但不要频繁设问。
- 变量与公式片段用行内代码。
- 默认不用列表；只有并列条件确实更清楚时才用，最多 3 条。

### 禁止 AI / 读稿腔

尽量避免：

- “接下来我们来看”
- “我们可以看到”
- “显而易见 / 不难发现”
- “首先、其次、最后”机械三段式
- “综上所述”
- “需要注意的是”反复出现
- 把幻灯片标题和标签重新念一遍

一句超过约 40 个汉字时，通常应拆句。

## 5. panel 与 narration

`panel.body` 是屏幕上的讲解；`narration` 若存在，应是更口语的提词，不得直接复制 body。

## 6. panel 位置只是偏好

`panel.placement` 的 `left/right/top/bottom/auto` 表示作者希望的讲解窗方向。runtime 必须优先满足“局部完整可见”：如果该方向经过 zoom + 3D 透视后会裁切 camera/highlight 联合区域或造成遮挡，允许自动换到其他方向，并同步调整 3D spatial 姿态。

## 7. 示例

```json
{
  "id":"s02-02",
  "order":2,
  "kind":"zoom",
  "camera":{"mode":"anchor","anchorId":"a-queue-rise"},
  "panel":{
    "placement":"right",
    "title":"真正的转折点",
    "body":"先看曲线开始持续上弯的位置。关键不是某一瞬间到达速率更高，而是它连续高于服务能力；从这里起，队列没有机会被清空，等待时间才会越拖越长。"
  },
  "advance":"manual"
}
```
