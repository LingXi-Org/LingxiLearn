import { CapabilityPage } from '@/lib/lingxi/components/capability-page'
export function generateStaticParams() { return [{ slug: 'lingxi' }] }
export default function Page() { return <CapabilityPage title='博客文章 · 未接入' /> }
