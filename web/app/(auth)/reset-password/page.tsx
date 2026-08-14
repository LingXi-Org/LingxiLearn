import type { Metadata } from 'next'
import ResetPasswordPage from '@/app/(auth)/reset-password/reset-password-content'

export const metadata: Metadata = { title: '重置密码' }
export const dynamic = 'force-dynamic'

export default ResetPasswordPage
