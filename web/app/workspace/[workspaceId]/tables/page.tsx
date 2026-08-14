import { LingxiResourcePage } from '@/app/workspace/[workspaceId]/components/lingxi-resource-page'
export function generateStaticParams() { return [{ workspaceId: 'lingxi' }] }
export default function Page() { return <LingxiResourcePage kind='tables' /> }
