export function LoadingState({ label = 'Loading…' }: { label?: string }) {
  return <div className='state-message'>{label}</div>
}

export function EmptyState({ title, description }: { title: string; description: string }) {
  return (
    <div className='empty-state'>
      <span className='eyebrow'>Ready when you are</span>
      <h2>{title}</h2>
      <p>{description}</p>
    </div>
  )
}

export function ErrorState({ message }: { message: string }) {
  return <div className='error-message'>{message}</div>
}
