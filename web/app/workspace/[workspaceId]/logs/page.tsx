import Logs from './logs'

export function generateStaticParams() { return [{ workspaceId: 'lingxi' }] }
export default function Page() { return <Logs /> }
