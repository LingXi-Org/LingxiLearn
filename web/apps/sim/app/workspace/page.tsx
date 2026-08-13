import { redirect } from 'next/navigation'

/** Lingxi has one virtual workspace; keep Sim's public entry point stable. */
export default function WorkspacePage() {
  redirect('/workspace/lingxi/home')
}
