import { notFound } from 'next/navigation'
export function generateStaticParams() { return [{ workspaceId: 'lingxi', credentialId: 'not-integrated' }] }
export default function Page() { notFound() }
