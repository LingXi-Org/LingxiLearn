import { redirect } from 'next/navigation'

export function generateStaticParams() {
  return [{ identifier: 'lingxi' }]
}

export default async function Page({ params }: { params: Promise<{ identifier: string }> }) {
  const { identifier } = await params
  redirect(
    identifier === 'lingxi'
      ? '/workspace/lingxi/home'
      : `/workspace/lingxi/chat/${encodeURIComponent(identifier)}`
  )
}
