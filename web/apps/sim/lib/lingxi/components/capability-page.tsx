export function CapabilityPage({ title }: { title: string }) {
  return (
    <div className='h-full overflow-y-auto bg-[var(--bg)]'>
      <div className='flex min-h-[320px] items-center justify-center p-8'>
        <div className='max-w-md rounded-[12px] border border-[var(--border-1)] bg-[var(--surface-2)] p-6 text-center'>
          <h2 className='font-medium text-[var(--text-primary)]'>{title}</h2>
          <p className='mt-2 text-[13px] leading-5 text-[var(--text-muted)]'>未接入</p>
        </div>
      </div>
    </div>
  )
}
