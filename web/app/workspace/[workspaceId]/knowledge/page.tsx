import { Knowledge } from './knowledge'

export function generateStaticParams() { return [{ workspaceId: 'lingxi' }] }
export default function Page() { return <Knowledge /> }
