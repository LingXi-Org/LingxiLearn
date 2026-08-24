/**
 * Field copy shared by every skill editing surface. The two pages share JSX via
 * `SkillFields`, but the canvas modal must frame its fields with
 * `ChipModalField` — required inside a `ChipModalBody` — so it cannot. These
 * strings are what keep the modal in step with the pages.
 */

export const SKILL_NAME_PLACEHOLDER = 'my-skill-name'
export const SKILL_NAME_HINT = '仅使用小写字母、数字和连字符（例如 my-skill）'
export const SKILL_DESCRIPTION_PLACEHOLDER = '说明此技能的用途和适用场景…'
export const SKILL_CONTENT_PLACEHOLDER = '使用 Markdown 编写技能说明…'

export const skillCopy = {
  title: '技能',
  searchPlaceholder: '搜索技能…',
  loadFailed: '技能加载失败，请稍后重试。',
  nameRequired: '请输入名称',
  nameTooLong: '名称不能超过 64 个字符',
  nameFormat: '名称仅可包含小写字母、数字和连字符（例如 my-skill）',
  descriptionRequired: '请输入描述',
  contentRequired: '请输入内容',
  nameConflict: '该技能名称已被占用。',
} as const

/** Mirrors `skillDescriptionSchema` in the contract. */
export const SKILL_DESCRIPTION_MAX_LENGTH = 1024
