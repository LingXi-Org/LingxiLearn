export function generateStaticParams() { return [{ workspaceId: 'lingxi' }] }
import { LingxiResourcePage } from '@/app/workspace/[workspaceId]/components/lingxi-resource-page'
export default function Page() { return <LingxiResourcePage kind='files' /> }
