'use client'

import { SocketProvider } from '@/app/workspace/providers/socket-provider'

interface WorkspaceRootLayoutProps {
  children: React.ReactNode
}

export default function WorkspaceRootLayout({ children }: WorkspaceRootLayoutProps) {
  return (
    <SocketProvider>
      <div className='workspace-root'>{children}</div>
    </SocketProvider>
  )
}
