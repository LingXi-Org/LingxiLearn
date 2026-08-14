import { LingxiDocumentDetail } from '@/app/workspace/[workspaceId]/components/lingxi-resource-page'
export function generateStaticParams() { return [{ workspaceId: 'lingxi', id: 'not-integrated', documentId: 'not-integrated' }] }
export default async function Page({ params }: { params: Promise<{ id: string; documentId: string }> }) { const { id, documentId } = await params; return <LingxiDocumentDetail baseId={id} documentId={documentId} /> }
