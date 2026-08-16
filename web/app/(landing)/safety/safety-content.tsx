import { type LegalPageConfig, ProseLink } from '@/app/(landing)/components/prose-page'

/** LingXi 安全与开放说明：数据隐私、教育边界、可追溯、开源复现、依赖与生态。 */
export const SAFETY_CONFIG: LegalPageConfig = {
  title: '安全与开放',
  description:
    'LingXi（灵犀智学）在学习数据隐私、教育安全边界、结果可追溯、开源复现、第三方依赖与开放生态方面的承诺和实践。',
  lastUpdated: '2026年8月16日',
  intro: [
    {
      kind: 'paragraph',
      content:
        'LingXi（灵犀智学）是一个面向学习任务的 AI 学习工作台。安全与开放不是两件分开的事：我们用清晰的数据边界、明确的教育定位和可追溯的运行证据来建立信任，再用开源代码、公开文档和可复现的部署来接受检验。本页说明我们在这六个方面的现状和实践。',
    },
    {
      kind: 'paragraph',
      content: '本页是概览性说明。具有约束力的完整条款见服务条款，数据处理细节见隐私政策。',
    },
    {
      kind: 'paragraph',
      content:
        '我们会随着学习功能、模型接入和部署方式的变化更新本页；如页面说明与服务条款或隐私政策存在差异，以后两者的最新版本为准。',
    },
  ],
  sections: [
    {
      id: 'privacy',
      heading: '一、学习数据隐私',
      blocks: [
        {
          kind: 'paragraph',
          content:
            'LingXi 只收集提供学习服务所必要的信息：账户身份、学习目标、任务与作答记录、知识资源引用和必要的运行状态。我们按“最小化、授权、可删除”三条原则处理这些数据。',
        },
        {
          kind: 'list',
          items: [
            '最小化：学习画像只保留影响下一步教学决策的字段，不无限累积对话历史。',
            '授权：学习数据在账户与工作区范围内隔离，未成年人的使用需要监护人同意。',
            '脱敏与删除：诊断和报告使用聚合信号；你可以导出或删除自己的学习数据，删除后不再参与任何诊断。',
          ],
        },
        {
          kind: 'paragraph',
          content: (
            <>
              完整的数据类别、保留期限、第三方共享范围和监护人权利，见
              <ProseLink href='/privacy'>隐私政策</ProseLink>。
            </>
          ),
        },
      ],
    },
    {
      id: 'boundaries',
      heading: '二、教育安全边界',
      blocks: [
        {
          kind: 'paragraph',
          content:
            'LingXi 的定位是 AI 辅助学习，不是替代教师、学校或专业教育机构的教学与评价。我们把这个边界落实到产品行为里，而不是只写在文档里。',
        },
        {
          kind: 'list',
          items: [
            '作业辅导优先给分步提示、错因分析和同类题训练，不默认输出整题答案。',
            '学习诊断用于辅助学习路径决策，不构成对学生能力的最终判定。',
            '讲解、练习与验证结论都保留依据和不确定性说明，低置信度时明确提示并降级处理。',
          ],
        },
        {
          kind: 'paragraph',
          content: (
            <>
              服务使用的具体条款和教育用途限制，见
              <ProseLink href='/terms'>服务条款</ProseLink>。
            </>
          ),
        },
      ],
    },
    {
      id: 'traceability',
      heading: '三、结果可追溯',
      blocks: [
        {
          kind: 'paragraph',
          content:
            'LingXi 的每个学习结论都应该能回答“从哪里来”。智能体运行保留任务上下文、工具调用摘要、阶段状态和生成产物索引；学习诊断保留数据来源、时间范围和处理依据。',
        },
        {
          kind: 'list',
          items: [
            '讲解与答案标注知识依据和来源片段，而不是不可解释的黑盒输出。',
            '路径调整、难度变化和掌握状态更新都记录触发原因。',
            '异常、低置信度和降级路径有专门的运行记录，便于复盘失败场景。',
          ],
        },
        {
          kind: 'paragraph',
          content: (
            <>
              运行证据的组织方式和日志视图说明，见
              <ProseLink href='/logs'>运行日志</ProseLink> 页面。
            </>
          ),
        },
      ],
    },
    {
      id: 'open-source',
      heading: '四、开源与复现',
      blocks: [
        {
          kind: 'paragraph',
          content: (
            <>
              LingxiLearn 的前端与服务端源码在
              <ProseLink href='https://github.com/LingXi-Org/LingxiLearn'>
                GitHub（LingXi-Org/LingxiLearn）
              </ProseLink>{' '}
              开放维护，组织主页为
              <ProseLink href='https://github.com/LingXi-Org'>LingXi-Org</ProseLink>。代码、教学
              Skills、部署配置和示例任务随仓库一起发布。
            </>
          ),
        },
        {
          kind: 'list',
          items: [
            '仓库包含完整的构建与部署说明，可以按文档从零复现一套本地环境。',
            '教学能力以 Skills 形式组织，可组合、可复用、可审查。',
            '重要修复和行为变化通过提交历史公开可查。',
          ],
        },
      ],
    },
    {
      id: 'dependencies',
      heading: '五、第三方依赖',
      blocks: [
        {
          kind: 'paragraph',
          content:
            'LingXi 的学习能力依赖第三方模型与基础服务。我们在意两件事：依赖是什么，以及依赖失败时会发生什么。',
        },
        {
          kind: 'list',
          items: [
            '模型服务：通过可配置的模型接入层使用 DeepSeek、Coze 等服务，密钥归用户所有，不混入学习记录。',
            '基础组件：前端与运行时使用开源库，许可证与版本以仓库依赖清单为准。',
            '降级策略：外部模型或检索不可用时，任务进入明确的失败或降级路径，不静默编造结果。',
          ],
        },
        {
          kind: 'paragraph',
          content: (
            <>
              支持的模型与接入方式说明，见
              <ProseLink href='/models'>模型页面</ProseLink>。
            </>
          ),
        },
      ],
    },
    {
      id: 'ecosystem',
      heading: '六、开放生态',
      blocks: [
        {
          kind: 'paragraph',
          content: (
            <>
              LingXi 的后端运行时 LingxiGraph 以 Agent Graph Runtime
              的形式提供服务，架构与接口文档发布在
              <ProseLink href='https://docs.lingxilearn.cn/docs/zh/'>docs.lingxilearn.cn</ProseLink>
              。我们欢迎开发者基于文档参与集成、扩展教学 Skills 或复现实验结果。
            </>
          ),
        },
        {
          kind: 'list',
          items: [
            'LingxiGraph：学习任务的调度、执行与追踪运行时，文档公开维护。',
            '教学 Skills：面向讲解、练习、诊断与验证的可组合教育能力单元。',
            '社区协作：问题反馈与改进建议通过仓库 Issue 和团队邮箱接收。',
          ],
        },
        {
          kind: 'paragraph',
          content: (
            <>
              想与团队直接交流，请访问
              <ProseLink href='/contact'>灵犀团队</ProseLink> 页面。
            </>
          ),
        },
      ],
    },
  ],
}
