import { KnowledgeBase } from './base'

export function generateStaticParams() { return [{ workspaceId: 'lingxi', id: 'not-integrated' }] }
export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params
  return <KnowledgeBase id={id} />
}
