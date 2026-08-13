import { NotIntegrated } from '@/ee/not-integrated'

export function CapabilityPage({ title }: { title: string }) {
  return (
    <div className='h-full overflow-y-auto bg-[var(--bg)]'>
      <NotIntegrated title={title} />
    </div>
  )
}
