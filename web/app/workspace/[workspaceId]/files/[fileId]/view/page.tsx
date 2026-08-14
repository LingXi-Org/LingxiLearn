import { LingxiFileDetail } from '@/app/workspace/[workspaceId]/components/lingxi-resource-page'
export function generateStaticParams() { return [{ workspaceId: 'lingxi', fileId: 'not-integrated' }] }
export default async function Page({ params }: { params: Promise<{ fileId: string }> }) { const { fileId } = await params; return <LingxiFileDetail fileId={fileId} /> }
