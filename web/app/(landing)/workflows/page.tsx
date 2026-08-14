import { notFound } from 'next/navigation'

export const metadata = { title: 'Not Found' }

export default function Page() {
  notFound()
}
