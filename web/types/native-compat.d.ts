interface Window {
  __ENV?: Record<string, string | undefined>
  simDesktop?: import('@sim/desktop-bridge').SimDesktopApi
}

declare module 'lru-cache' {
  export interface Options<K, V> {
    max?: number
    ttl?: number
    updateAgeOnGet?: boolean
    dispose?: (value: V, key: K, reason: string) => void
  }

  export class LRUCache<K, V> {
    constructor(options?: Options<K, V>)
    get(key: K): V | undefined
    set(key: K, value: V): this
    has(key: K): boolean
    delete(key: K): boolean
    clear(): void
    forEach(callback: (value: V, key: K, cache: LRUCache<K, V>) => void): void
  }
}

declare module 'fluent-ffmpeg' {
  export interface FfmpegStream {
    codec_type?: string
    codec_name?: string
    sample_rate?: number | string
    channels?: number
    width?: number
    height?: number
  }

  export interface FfmpegMetadata {
    streams: FfmpegStream[]
    format: {
      duration?: number
      format_name?: string
      bit_rate?: number | string
    }
  }

  export interface FfmpegCommand {
    toFormat(format: string): this
    audioCodec(codec: string): this
    audioChannels(channels: number): this
    audioFrequency(frequency: number): this
    audioBitrate(bitrate: number): this
    input(input: string): this
    inputOptions(options: readonly string[]): this
    outputOptions(options: readonly string[]): this
    complexFilter(filters: readonly string[]): this
    videoFilters(filters: string | readonly string[]): this
    audioFilters(filters: readonly string[]): this
    setStartTime(seconds: number): this
    noVideo(): this
    frames(count: number): this
    on(event: 'end', listener: () => void): this
    on(event: 'error', listener: (error: Error) => void): this
    save(path: string): this
  }

  export function setFfmpegPath(path: string): void
  export function ffprobe(
    path: string,
    callback: (error: Error | null, metadata: FfmpegMetadata) => void
  ): void
  function ffmpeg(input?: string): FfmpegCommand
  export default ffmpeg
}

declare module 'js-yaml' {
  export function load(input: string): unknown
}

declare module 'jsdom' {
  export class JSDOM {
    constructor(html?: string)
    readonly window: Window
  }
}

declare module 'busboy' {
  import type { Readable } from 'node:stream'

  export interface FileInfo {
    filename: string
    encoding: string
    mimeType: string
  }

  export interface Busboy {
    on(event: 'field', listener: (name: string, value: string) => void): this
    on(event: 'file', listener: (name: string, stream: Readable, info: FileInfo) => void): this
    on(event: 'error', listener: (error: Error) => void): this
    on(event: 'close', listener: () => void): this
    destroy(): void
  }

  export interface BusboyOptions {
    headers: Record<string, string>
    limits?: { fileSize?: number; files?: number }
  }

  function busboy(options: BusboyOptions): Busboy
  export default busboy
}

declare module 'heic-decode' {
  export interface HeicImage {
    width: number
    height: number
  }

  export interface HeicImageCollection extends Array<HeicImage> {
    dispose(): void
  }

  export function all(options: { buffer: Buffer }): Promise<HeicImageCollection>
}

declare module 'heic-convert' {
  function convert(options: { buffer: Buffer; format: 'JPEG' | 'PNG' }): Promise<Buffer>
  export default convert
}

declare module 'drizzle-kit' {
  export interface Config {
    schema: string
    out: string
    dialect: string
    dbCredentials: Record<string, string>
  }
}

declare module 'ssh2' {
  export interface Client {
    end(): void
    sftp(callback: (error: Error | undefined, channel: SFTPWrapper) => void): void
  }

  export interface SFTPWrapper {
    readFile(path: string, callback: (error: Error | undefined, data: Buffer) => void): void
    writeFile(
      path: string,
      data: string | Buffer,
      callback: (error: Error | undefined) => void
    ): void
  }
}

declare module 'micromatch' {
  export interface Options {
    bash?: boolean
    dot?: boolean
    windows?: boolean
    nobrace?: boolean
    noext?: boolean
  }

  export function isMatch(
    input: string,
    pattern: string | readonly string[],
    options?: Options
  ): boolean

  const micromatch: { isMatch: typeof isMatch }
  export default micromatch
}

declare module 'nodemailer' {
  export interface MailAttachment {
    filename?: string
    content: string | Buffer
    contentType?: string
    contentDisposition?: string
  }

  export interface MailOptions {
    from?: string
    to?: string | readonly string[]
    subject?: string
    html?: string
    text?: string
    replyTo?: string
    headers?: Record<string, string | readonly string[]>
    attachments?: readonly MailAttachment[]
  }

  export interface SentMessageInfo {
    messageId?: string
  }

  export interface TransportOptions {
    host?: string
    port?: number
    secure?: boolean
    auth?: { user: string; pass: string }
    SES?: { sesClient: unknown; SendEmailCommand: unknown }
  }

  export interface Transporter {
    sendMail(options: MailOptions): Promise<SentMessageInfo>
  }

  const nodemailer: {
    createTransport(options?: TransportOptions): Transporter
  }
  export default nodemailer
}

declare module 'nodemailer/lib/mail-composer' {
  import type { MailOptions } from 'nodemailer'

  export interface MailComposerOptions extends MailOptions {}

  export default class MailComposer {
    constructor(options: MailComposerOptions)
    compile(): {
      build(callback: (error: Error | undefined, message: Buffer) => void): void
    }
  }
}

declare module 'nodemailer/lib/ses-transport' {
  namespace SESTransport {
    interface Options {
      SES?: { sesClient: unknown; SendEmailCommand: unknown }
    }
  }

  const SESTransport: SESTransport.Options
  export default SESTransport
}

declare module 'html-to-text' {
  export interface SelectorOptions {
    selector: string
    format?: string
    options?: Record<string, boolean | number | string>
  }

  export interface ConvertOptions {
    wordwrap?: false | number
    selectors?: readonly SelectorOptions[]
    preserveNewlines?: boolean
  }

  export function convert(input: string, options?: ConvertOptions): string
  export function htmlToText(input: string, options?: ConvertOptions): string
}
