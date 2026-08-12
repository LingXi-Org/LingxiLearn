# HTML 幻灯片生成规范 v2

每一页 = 一个自包含 `.html`，固定 1280×720。页面是 PPT，不是网页。

## 1. 文件与页角色

```text
slides/s01.html ... slides/sNN.html
```

根节点必须同时声明：

```html
<div class="slide"
     id="s02"
     data-slide-id="s02"
     data-slide-role="content"
     data-canvas="1280x720"
     data-style="anthropic-academic">
```

`data-slide-role`：

- 第一页：`opening`
- 中间：`content`
- 最后一页：`closing`

## 2. 根节点硬约束

```css
html,body{margin:0;padding:0;background:#141412;}
.slide{
  position:relative;
  width:1280px;
  height:720px;
  overflow:hidden;
  background:var(--paper);
  color:var(--ink-1);
}
```

禁止 `@media`、`vw/vh`、百分比定位、自动响应式布局。所有直接内容块都用绝对定位。

## 3. 主视觉对象

正文页至少一个元素带：

```html
<div class="block visual" data-visual="diagram" ...>...</div>
```

或：

```html
<svg class="block visual" data-visual="chart" ...>...</svg>
```

推荐类型：`diagram / chart / process / timeline / comparison / formula / geometry / system / table / image / concept-map`。

**视觉对象不是装饰图。** 它必须承载本页核心关系，并优先占据中部 50–70% 空间。

### SVG 文字

所有 `<svg><text>` 必须带 `.t / .ts / .th / .tn` 之一；正文不直接写死 fill 色。

## 4. 文字规范

- opening 主标题 1–2 行；副标题只保留一句课程承诺。
- content 页标题必须是结论句或问题句；建议 ≤18 个汉字。
- 正文总量目标 ≤100 等价单位，严格上限 140。
- bullet ≤3 条；不要写 5–8 条提纲。
- 图注解释“图说明了什么”，不是重复标题。
- closing 只保留 2–3 个可带走的结论。

## 5. 锚点

```html
<div class="block visual"
     data-visual="formula"
     data-anchor="a-window-growth"
     data-rect="96 224 720 312"
     style="left:96px;top:224px;width:720px;height:312px;">
```

必须：

1. `data-anchor` 全 deck 唯一；
2. `data-rect="x y w h"`；
3. inline `left/top/width/height` 与其一致。

优先给视觉局部设锚点：一段曲线、一个机制链、一个对比分区、一个公式结构。
不要给标题、页码、装饰、单字符设锚点。

## 6. 样式禁止项

| 禁止 | 原因 |
|---|---|
| `<script>` | 幻灯片必须是纯静态可信内容 |
| 外链 / 网络字体 / 远程图片 | 离线与可复现 |
| `position:fixed/sticky` | 与外层相机冲突 |
| CSS transition / animation | 动效全部由 runtime 控制 |
| 渐变 / shadow / blur / glow | 违反 Anthropic 学术平面风 |
| 字重 >500 | 违反学术风层级 |
| 3D 数据图表 | 透视会扭曲数据；3D 仅属于 runtime 镜头 |
| emoji | 用 SVG 形状或文字 |
| 大段正文 | 解释应进入 panel |

## 7. 版式

见 `assets/templates/layouts.md`。优先采用“标题 + 一个主视觉 + 少量辅助注释”的版式；
`title-body` 式纯文本布局已废弃，不再作为正文页默认方案。

## 8. 自查

- [ ] opening / content / closing 角色正确
- [ ] content 页存在 `data-visual`
- [ ] 主视觉占主导，不是卡片堆叠
- [ ] 可见文字明显少于图形信息
- [ ] 只用 400/500 字重；无渐变、阴影、模糊
- [ ] SVG text 有 t/ts/th/tn 类
- [ ] 锚点覆盖完整可解释对象
- [ ] 页面无脚本、外链、响应式、动画
