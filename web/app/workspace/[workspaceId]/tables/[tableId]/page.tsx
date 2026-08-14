import { LingxiTableDetail } from '@/app/workspace/[workspaceId]/components/lingxi-resource-page'
export function generateStaticParams() { return [{ workspaceId: 'lingxi', tableId: 'not-integrated' }] }
export default async function Page({ params }: { params: Promise<{ tableId: string }> }) { const { tableId } = await params; return <LingxiTableDetail tableId={tableId} /> }
