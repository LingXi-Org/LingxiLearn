import { Tables } from './tables'

export function generateStaticParams() { return [{ workspaceId: 'lingxi' }] }
export default function Page() { return <Tables /> }
