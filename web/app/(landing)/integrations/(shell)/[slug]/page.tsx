import { notFound } from 'next/navigation'
export function generateStaticParams() {
  return [{ slug: 'lingxi' }]
}
export default function Page() {
  notFound()
}
