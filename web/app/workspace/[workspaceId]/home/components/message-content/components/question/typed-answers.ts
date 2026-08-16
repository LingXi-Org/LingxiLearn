/**
 * The question card's answer shape, in option-id form (issue #18 §10.5).
 *
 * Kept apart from the React component on purpose: this is the whole payload a
 * typed interaction submits, so it is a pure function the contract tests can
 * exercise without a DOM. The card renders labels; it never answers with them.
 */

import type { QuestionItem } from '@/app/workspace/[workspaceId]/home/components/message-content/components/special-tags/special-tags'

export interface TypedQuestionAnswer {
  /** Position in the rendered batch; the owner maps it to its question id. */
  questionIndex: number
  selectedOptionIds: string[]
  /** The "Something else" text, when it counts toward the answer. */
  text: string
}

/**
 * One typed answer per question in the batch, preserving option order.
 *
 * ``selectionsByStep`` holds option ids; ``customsByStep`` holds the typed
 * "Something else" entry already filtered for whether it counts (a
 * multi_select custom only counts while its checkbox is checked).
 */
export function collectTypedAnswers(
  data: QuestionItem[],
  selectionsByStep: string[][],
  customsByStep: string[]
): TypedQuestionAnswer[] {
  return data.map((question, index) => {
    const selected = new Set(selectionsByStep[index] ?? [])
    return {
      questionIndex: index,
      // Option order, not click order: the same selection always serializes
      // the same way, so a replayed answer is byte-identical.
      selectedOptionIds: question.options
        .map((option) => option.id)
        .filter((id) => selected.has(id)),
      text: (customsByStep[index] ?? '').trim(),
    }
  })
}

/**
 * A step's combined answer for display: selected option labels in option
 * order, with the typed entry appended last.
 */
export function answerLabelsFor(
  question: QuestionItem,
  selectedOptionIds: string[],
  custom: string
): string[] {
  const selected = new Set(selectedOptionIds)
  const ordered = question.options
    .filter((option) => selected.has(option.id))
    .map((option) => option.label)
  return custom.trim() ? [...ordered, custom.trim()] : ordered
}
