export function generateStaticParams() {
  return [{ organizationId: 'lingxi' }]
}

export default function OrganizationSettingsLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>
}
