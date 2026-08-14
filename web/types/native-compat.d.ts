interface Window {
  __ENV?: Record<string, string | undefined>
}

declare module 'ssh2' {
  export type Client = any
  export type SFTPWrapper = any
}

declare module 'micromatch' {
  export interface Options { [key: string]: unknown }
  const micromatch: any
  export default micromatch
}

declare module 'nodemailer' {
  export interface Transporter { sendMail(options: any): Promise<any> }
  const nodemailer: any
  export default nodemailer
}

declare module 'nodemailer/lib/mail-composer' {
  const MailComposer: any
  export default MailComposer
}

declare module 'nodemailer/lib/ses-transport' {
  namespace SESTransport { interface Options { [key: string]: any } }
  const SESTransport: any
  export default SESTransport
}

declare module 'html-to-text' {
  export function convert(input: string, options?: any): string
}
