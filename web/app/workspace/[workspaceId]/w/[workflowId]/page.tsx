import { LingxiWorkflow } from '@/lib/lingxi/components/lingxi-workflow'

export function generateStaticParams() {
  return [{ workspaceId: 'lingxi', workflowId: 'lingxi' }]
}

export default async function Page({
  params,
}: {
  params: Promise<{ workspaceId: string; workflowId: string }>
}) {
  const { workflowId } = await params
  const taskId = workflowId.startsWith('lingxi-task-')
    ? workflowId.slice('lingxi-task-'.length)
    : ''

  if (!taskId) {
    return (
      <div className='flex h-full items-center justify-center text-sm text-[var(--text-secondary)]'>
        请从对话资源中打开 Lingxi 智能体编排图。
      </div>
    )
  }

  return <LingxiWorkflow taskId={taskId} />
}
