import { Table } from './table'

export function generateStaticParams() { return [{ workspaceId: 'lingxi', tableId: 'not-integrated' }] }
export default async function Page({ params }: { params: Promise<{ tableId: string }> }) {
  const { tableId } = await params
  return <Table tableId={tableId} />
}
