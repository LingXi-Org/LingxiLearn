import { Table } from './table'
import { LingxiTableDetail } from '../../components/lingxi-resource-page'

export function generateStaticParams() { return [{ workspaceId: 'lingxi', tableId: 'not-integrated' }] }
export default async function Page({ params }: { params: Promise<{ workspaceId: string; tableId: string }> }) {
  const { workspaceId, tableId } = await params
  return workspaceId === 'lingxi' ? <LingxiTableDetail tableId={tableId} /> : <Table tableId={tableId} />
}
