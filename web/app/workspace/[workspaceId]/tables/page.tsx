import { Tables } from './tables'
import { TablesPage } from '../components/lingxi-resource-page'

export function generateStaticParams() { return [{ workspaceId: 'lingxi' }] }
export default function Page({ params }: { params: Promise<{ workspaceId: string }> }) {
  return <PageContent params={params} />
}

async function PageContent({ params }: { params: Promise<{ workspaceId: string }> }) {
  const { workspaceId } = await params
  return workspaceId === 'lingxi' ? <TablesPage /> : <Tables />
}
