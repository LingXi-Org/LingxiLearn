import { Files } from '../files'

export function generateStaticParams() { return [{ workspaceId: 'lingxi', fileId: 'not-integrated' }] }
export default function Page() {
  return <Files />
}
