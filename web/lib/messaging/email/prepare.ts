import type { EmailOptions, ProcessedEmailData } from '@/lib/messaging/email/types'
import { getFromEmailAddress, hasEmailHeaderControlChars } from '@/lib/messaging/email/utils'

function sanitizeEmailSubject(subject: string): string {
  return subject.replace(/[\r\n]+/g, ' ').trim()
}

function validateAndSanitize(options: EmailOptions): {
  senderEmail: string
  subject: string
  replyTo?: string
} {
  const senderEmail = options.from || getFromEmailAddress()
  const recipients = Array.isArray(options.to) ? options.to : [options.to]

  if (recipients.some(hasEmailHeaderControlChars)) {
    throw new Error('Invalid recipient email header')
  }
  if (hasEmailHeaderControlChars(senderEmail)) {
    throw new Error('Invalid from email header')
  }
  if (options.replyTo && hasEmailHeaderControlChars(options.replyTo)) {
    throw new Error('Invalid reply-to email header')
  }

  const subject = sanitizeEmailSubject(options.subject)
  if (subject.length === 0) {
    throw new Error('Email subject cannot be empty')
  }

  return { senderEmail, subject, replyTo: options.replyTo }
}

export function processEmailData(options: EmailOptions): ProcessedEmailData {
  const { senderEmail, subject, replyTo } = validateAndSanitize(options)
  const {
    to,
    html,
    text,
    attachments,
  } = options

  return {
    to,
    subject,
    html,
    text,
    senderEmail,
    headers: {},
    attachments,
    replyTo,
  }
}
