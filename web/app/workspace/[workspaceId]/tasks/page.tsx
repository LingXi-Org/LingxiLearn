import { TaskBoard } from '@/features/agent-task/task-board'

export default async function TasksPage({ params }: { params: Promise<{ workspaceId: string }> }) {
  const { workspaceId } = await params
  return <TaskBoard workspaceId={workspaceId} />
}
