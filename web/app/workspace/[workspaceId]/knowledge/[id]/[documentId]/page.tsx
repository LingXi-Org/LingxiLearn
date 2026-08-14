import { Document } from './document'

export function generateStaticParams() { return [{ workspaceId: 'lingxi', id: 'not-integrated', documentId: 'not-integrated' }] }
export default async function Page({ params }: { params: Promise<{ id: string; documentId: string }> }) {
  const { id, documentId } = await params
  return <Document knowledgeBaseId={id} documentId={documentId} />
}
