# 主智能体调用契约 v2.4

输入仍接受 `zoom-lecture-task/v1` 结构或自然语言；教学数据继续使用 `zoom-lecture/v2`。发布物保持单文件离线，同时 runtime 必须执行 protected-view 几何求解，保证每个 zoom 目标完整可见。

## 1. 缺省值

| 字段 | 默认 |
|---|---|
| canvas | `ppt169` |
| language | `zh-CN` |
| style | `anthropic-academic` |
| density | `balanced`，但受 v2 视觉密度硬约束覆盖 |
| zoomPointsPerSlide | content 页 2–4 |
| qualityMode | `fast` |

`slideCount` 表示**总页数，包含 opening 与 closing**；不得少于 3。

默认总页数：problem 5–7；concept 6–8；lesson 8–12。

### 1.1 质量路径

`constraints.qualityMode` 可选：

- `fast`：默认路径。只加载任务、页面 authoring、讲解数据和所用模板；一次性完成大纲与页面，
  最后统一构建和严格校验；默认不运行浏览器量测。
- `full`：完整路径。用于自定义样式/密度、复杂 protected-view 几何、内容驱动锚点、像素级
  视觉审查或调用方明确要求的演示级 QA；允许加载全部设计参考并运行临时量测/渲染检查。

缺少 `qualityMode` 时按 `fast` 处理。无论路径如何选择，严格校验、离线 bundle、runtime
protected-view 求解和最终完整性保护都不能跳过。

## 2. 输出目录

```text
<outputDir>/
├── slides/
├── runtime/
│   └── index.html
├── dist/
│   └── lecture.html
├── lecture.json
└── manifest.json
```

`assets/runtime/index.html` 是 Skill 内的源码模板；工程中的 `runtime/index.html` 与 `dist/lecture.html` 是学习者使用的产物，二者都必须存在。

## 3. 发布构建

生成 deck 后必须执行：

```bash
python3 scripts/build_standalone.py <outputDir>
```

构建脚本在生成阶段把 `lecture.json` 与所有 slide HTML 内联进 runtime。默认一次性生成所有页面后再
执行构建；不要逐页重复构建或重新规划。若校验失败，只针对失败项修复并重新执行最终检查。
最终 `dist/lecture.html`：

- 直接双击可运行；
- 不需要 Python / Node / HTTP server；
- 不依赖 CDN；
- 不在运行时读取旁路 JSON / HTML 文件；
- 每个 zoom 最终 3D 姿态下 camera/highlight 联合目标完整位于 viewport 且不被 panel 遮挡；
- 为满足完整展示允许自动降低预设倍率、更换 panel 方向，并露出纸面之外的纯白背景。

## 4. 任务补全

自然语言输入缺字段时不要反问。自行补：受众、2–4 个学习目标、视觉大纲、总页数、页面结论与 zoom 点；所有推断写入 `manifest.assumptions`。不要生成或比较候选大纲。

## 5. 回执

默认返回主要学习者交付物和简短回执：

- `dist/lecture.html`（单文件离线发布物）
- 总页数 / content 页数 / step 数
- 严格校验结果
- assumptions / deviations

`lecture.json`、`runtime/index.html`、`slides/` 和 `manifest.json` 仍须在项目工程中按需生成，
用于构建、对齐和严格校验；只有在调用方明确要求源工程包或检查这些文件时才单独回传。
不要回传截图、图片、PPT/PPTX、重复 HTML/JSON 副本或其他临时文件。

不要粘贴完整 HTML 或 JSON。
