# Zoom + Spatial Perspective Runtime Contract v2.3

本契约定义标准 runtime 如何解释 `lecture.json`。页面不是“被缩放的一张截图”，而是 **3D 空间中的二维纸面**。课程镜头、空间转场和用户自由查看必须使用独立 transform 层。最终学习者交付必须支持**单 HTML 离线运行**。

## 1. 2D 课程相机

画布 `W=1280,H=720`。锚点中心归一化：

```text
cx = (x + w/2) / W
cy = (y + h/2) / H
```

倍率：

| depth | scale |
|---:|---:|
|1|1.25|
|2|1.50|
|3|1.80|
|4|2.20|
|5|3.50|
|6|5.00|

若 depth / scale 均缺省：

```text
sFit = min(W/(w+2*padding), H/(h+2*padding))
scale = clamp(sFit,1.05,6.0)
```

焦点不再做“必须留在幻灯片纸张内部”的边缘钳制。`focus.cx/cy` 只限制在 `0..1`；最终镜头允许继续平移，使幻灯片纸面的一部分移出屏幕，并在外侧露出纯白背景。

基础 2D 变换：

```text
tx = W/2 - cx * W * scale
ty = H/2 - cy * H * scale
translate3d(tx,ty,0) scale(scale)
```

这只是初始候选。zoom + panel 的最终 `tx/ty/scale` 必须经过第 6 节的 protected-view 求解器再次校正。

相邻 zoom 直接从上一个相机状态插值到下一个状态，不先退回 overview。

## 2. Full-bleed Clean Runtime

运行时不得为了 UI chrome 压缩讲解画面：

```text
viewport { inset: 0; }
```

禁止在标准交付中出现：

- 顶部 brand / title 黑条；
- 底部播放控制黑条；
- 进度条与页码状态栏；
- zoom 百分比 / `FREE VIEW` 标签；
- `ready / zoom / free view` 等 debug 文本。

非 16:9 屏幕或局部镜头把纸面移出可视区时，纸面之外统一显示**纯白背景**。不得出现上下黑边。页面本体仍按完整 1280×720 `contain`，不能为了“填满”而裁切教学内容。

## 3. 3D Spatial UI Transition

标准层：

```text
viewport: perspective
fit-layer: screen fit
interaction-layer: free-view transform
spatial-layer: scripted translate3d + rotateX/Y/Z
camera: precise course zoom
```

严禁把四类变换合并到单一元素。

### 3.1 目标姿态

推荐默认：

- `perspective: 1400–1700px`，标准 runtime 为 `1500px`
- panel 在右：页面向左移，`rotateY(+6.5° ~ +8.0°)`
- panel 在左：页面向右移，`rotateY(-6.5° ~ -8.0°)`
- 左右姿态 pitch：约 `-1° ~ -2.4°`
- panel 在下：页面向上，`rotateX(-3° ~ -5°)`
- panel 在上：页面向下，`rotateX(+3° ~ +5°)`
- 最终 Z：轻微后退 `-10px ~ -30px`
- overview：回正视图

这必须足以让学生肉眼感知“纸面侧转”，但不能夸张到像 3D 卡片特效。

### 3.2 空间路径

不能只做 `transform: A → B` 的机械插值。标准 Spatial Transition 包含中间姿态：

1. 从当前姿态离开；
2. 纸面向后退（推荐 `z=-70 ~ -110px`）；
3. yaw 比最终姿态额外多转约 `2°–4°`；
4. 再向新的 anchor / panel 布局落定。

推荐总时长 `800–1050ms`，默认缓动 `cubic-bezier(.16,1,.3,1)`。

## 4. 用户自由查看层

- **滚轮**：连续缩放；默认范围约 `0.72×–2.45×`；尽量以鼠标位置附近为缩放中心。
- **左键拖拽**：连续平移，可根据位移附加最多约 `±5° yaw / ±3° pitch` 的轻微观察角。
- **双击 / 0**：复位自由查看层。
- **→ / Space / PageDown**：下一 step；**← / PageUp**：上一 step。
- panel 必须位于交互捕获层之上，保证 panel 滚动、链接和文字选择正常。

标准 runtime 不显示 zoom 数值标签。交互反馈来自画面本身，而不是 HUD。

### 自动镜头接管

用户自由查看后切换 step：

1. `interaction-layer` 在 `620–1000ms` 内柔和归零；
2. `camera` 同时移动到新的课程 anchor；
3. `spatial-layer` 同时完成 3D 空间路径；
4. 三者共享相近 easing 和时长。

最终课程锚点必须准确落位，但起点允许是用户当前任意自由视角。

## 5. 首次蓝色操作提示窗

opening 初始帧出现一次特殊的蓝色 onboarding 小窗。它不是课程讲解 panel，也不要模拟老师说话；只列必要操作：

```text
→ / Space · ←   下一步 / 上一步
鼠标滚轮          缩放
左键拖拽          移动画面
双击 / 0          恢复讲解视角
```

允许一个短按钮：`开始`。禁止欢迎语、解释性段落、拟人化承诺、教程式长句。方向键开始讲解时也可自动关闭。

## 6. Protected View：局部完整展示硬约束

这是 runtime 的**最高级几何约束**。作者在 `lecture.json` 写入的 `scale/depth/placement` 都是偏好，不得凌驾于完整展示。

### 6.1 受保护目标

每个 zoom step 的 protected target 是：

- `camera.anchorId` 对应矩形；
- `highlight.anchorIds` 若存在，与 camera anchor 取**联合包围框**。

最终状态必须同时满足：

1. 目标投影矩形完整位于 viewport 内；
2. 与 panel 不相交；
3. viewport 外缘至少保留约 `26px` 安全边距；
4. panel 与目标之间至少保留约 `28px` 间距。

### 6.2 必须按最终 3D 投影测量

不能只用二维 `anchor.rect × scale` 猜测。标准 runtime 必须维护一个不可见的 `geometry-probe`，复制最终的：

```text
fit → spatial transform → camera transform → protected target
```

并用浏览器 `getBoundingClientRect()` 取得经过 perspective / rotateX / rotateY / Z-depth 后的真实屏幕包围框。

### 6.3 求解顺序

进入 zoom 前：

1. 先按请求倍率和首选 panel 位置生成候选；
2. 测量 panel 的**实际**屏幕矩形（窄屏 CSS 可能把左右 panel 改成底部 panel）；
3. 从 panel 对侧生成 protected viewport；
4. 若目标投影比 protected viewport 大，先降低 camera scale；
5. 再平移 camera，消除上/下/左/右 overflow；
6. 比较 `preferred / opposite / left / right / top / bottom` 候选，选择能保持目标完整且倍率最高的布局；
7. 最终仍不能把目标挡在 panel 下方；
8. 动画落定后再用真实 highlight DOM 做一次 final guard；若仍发现裁切/遮挡，必须再保守降倍率并修正位置。

`panel.placement` 因此是**优先方向而不是绝对命令**。完整性冲突时允许 runtime 自动换边。

### 6.4 允许露白，不允许裁切

为了完整展示靠近页面边缘的对象，camera 可以平移到 1280×720 纸面之外。此时 viewport 暴露区域必须是纯白色。

> **宁可看到纸张之外的白色，也不能少看到目标的一角。**

### 6.5 空间转场中的原则

最终落位必须严格满足 protected-view。中间 bridge frame 应通过额外后退 Z 轴减小画面，避免在空间转身时制造明显裁切；不得为了 3D 戏剧性牺牲最终可读性。

## 7. panel 视觉与文字显现

常规讲解 panel：米白 / 白纸面、0.5px 发丝边界、衬线标题、无衬线正文、紫色只做细小强调，无玻璃、无发光、无重阴影。

文字显现不用逐字打字机：

- opacity `0→1`
- translateY `4–6px→0`
- blur `2px→0`
- 单 token `220–320ms`
- token 间隔约 `18–28ms`
- 总时长约 1.3s 以内

`prefers-reduced-motion` 时直接显示，并关闭空间中间帧动画。

## 8. 单文件编译契约

生成阶段执行：

```bash
python3 scripts/build_standalone.py <project_dir>
```

默认必须产生：

```text
<project_dir>/dist/lecture.html
```

编译产物内嵌：

- 完整 `lecture.json`；
- lecture 引用的全部 slide HTML；
- runtime CSS / JS。

slide 必须通过 `iframe.srcdoc` 或等价内嵌机制加载，不能在发布产物运行时再 `fetch()` 本地 JSON / HTML。Python、Node、CDN、HTTP server 都只能是生成阶段工具，不得成为学习者查看 lecture 的依赖。
