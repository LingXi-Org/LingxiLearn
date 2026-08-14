import { Files } from './files'

export function generateStaticParams() {
  return [{ workspaceId: 'lingxi' }]
}

export default function Page() {
  return <Files />
}
