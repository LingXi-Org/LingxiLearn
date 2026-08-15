# LingxiLearn 产品页组件目录

## 页面入口

主页：`web/app/(landing)/page.tsx` → `landing.tsx`。

主要介绍页：`workflows`、`files`、`tables`、`knowledge`、`solutions/{sales,it,hr,finance,engineering,compliance}`、`enterprise`、`integrations`、`pricing`、`contact`、`demo`、`learning`、`library`、`logs`、`models`、`careers`、`blog`、`changelog`、`privacy`、`terms`、`comparisons`。

## 主页可复用组件

| 视觉/功能 | 源码入口 | 适合改写 |
|---|---|---|
| 页面壳、导航、页脚 | `components/landing-shell`, `navbar`, `footer` | 品牌名、导航、CTA、全站包裹结构 |
| Hero 与 CTA | `components/hero`, `hero-cta`, `hero/components/hero-header` | 主标题、副标题、按钮、hero 视觉变体 |
| 产品演示 | `components/product-demo`、`landing-preview` | 演示数据、标签、预览视图 |
| 功能区 | `components/features` 下 `FeatureCard`、`CalloutFrame`、`BuildCallout`、`IntegrationsCallout`、`KnowledgeCallout`、`LogsCallout` | 功能文案、卡片数据、既有图形 |
| 信任与转化 | `trusted-by`、`logos`、`cta`、`landing-faq` | logo 列表、FAQ、转化文案与链接 |
| 动态/装饰视觉 | `mothership`、`platform-hero-visual`、`shared/hero-loop-shell`、`shared/editor-loop`、`shared/code-window-graphic` | 仅替换既有数据、代码片段、资源和内容 |

## 附属页模板与专属组件

- `SolutionsPage`：`components/solutions-page/solutions-page.tsx`；配置类型在 `types.ts`。用于 workflows、files、tables、knowledge、solutions 和部分 enterprise 页面。优先改对应页面的 `*_CONFIG`，不要复制模板。
- 解决方案内部组件：`solutions-hero`、`solutions-logos-row`、`solutions-card-row`、`solutions-visual-frame`、`solutions-structured-data`。卡片/hero/视觉框均有现成变体。
- 专属 hero loop：各页面 `components/*-hero-loop.tsx`，并复用 `shared/hero-loop-shell`；只修改数据和既有 stage。
- `ProsePage`：用于 `privacy`、`terms` 等长文页面；改对应 `*-content.tsx` / config。
- 内容模板：`content-index-page`、`content-post-page`、`content-author-page`、`content-tags-page`，配合 `back-link`、`share-button`、`content-image`、`json-ld`。
- 集成：`integrations/integration-grid`、`integration-card`、`integration-icon`、`request-integration-modal`；详情页还有 `integration-cta-button`、`template-card-button`。
- 占位页：`lib/lingxi/components/capability-page` 当前被 files/tables/knowledge 等 `page.tsx` 使用；若用户要求完整产品介绍，先改对应实现页而不是扩展占位组件。

## 静态资源范围

优先检查 `web/public/static`、`web/public/landing`、`web/public/templates`、`web/public/tooltips` 及组件旁的 `.module.css`/媒体引用。资源替换必须保持现有组件的尺寸、比例、加载方式和 alt 约定；没有新资源时只给出替换指导。
