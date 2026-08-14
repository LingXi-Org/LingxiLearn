import { Body, Container, Font, Head, Html, Img, Preview, Section } from '@react-email/components'
import { baseStyles } from '@/components/emails/_styles'
import { EmailFooter } from '@/components/emails/components/email-footer'
import { LINGXI_BRAND_ASSETS } from '@/lib/branding/lingxi-assets'
import { getBaseUrl } from '@/lib/core/utils/urls'
import { getBrandConfig } from '@/ee/whitelabeling'

/**
 * Canonical wordmark display size for email clients. The source is an SVG, so
 * both dimensions are supplied to keep the fallback layout stable.
 */
const WORDMARK_SIZE = { height: '29', width: '68' } as const

/** Whitelabeled logos are arbitrary aspect ratios, so only height is pinned. */
const CUSTOM_LOGO_SIZE = { height: '34' } as const

interface EmailLayoutProps {
  /** Preview text shown in email client list view */
  preview: string
  /** Email content to render inside the layout */
  children: React.ReactNode
  /** Optional: hide footer for internal emails */
  hideFooter?: boolean
  /**
   * Whether to show unsubscribe link in footer.
   * Set to false for transactional emails where unsubscribe doesn't apply.
   */
  showUnsubscribe: boolean
}

/**
 * Shared email layout wrapper providing consistent structure.
 * Includes Html, Head, Body, Container with logo header, and Footer.
 */
export function EmailLayout({
  preview,
  children,
  hideFooter = false,
  showUnsubscribe,
}: EmailLayoutProps) {
  const brand = getBrandConfig()
  const baseUrl = getBaseUrl()
  const hasCustomLogo = Boolean(brand.logoUrl)

  return (
    <Html>
      <Head>
        {/*
          `fallbackFontFamily` only accepts react-email's fixed union, so it
          cannot express the platform's full chain (`system-ui`, `Segoe UI`,
          `Roboto`, …) — this is the closest allowed subset. The complete chain
          lives on `typography.fontFamily`, which is applied inline to every
          element and is what clients that strip `@font-face` actually use.
        */}
        <Font
          fontFamily='Season Sans'
          fallbackFontFamily={['Helvetica', 'Arial', 'sans-serif']}
          webFont={{
            url: `${baseUrl}/brand/fonts/SeasonSansUprightsVF.woff2`,
            format: 'woff2',
          }}
          fontWeight='300 800'
          fontStyle='normal'
        />
      </Head>
      <Preview>{preview}</Preview>
      <Body style={baseStyles.main}>
        <Container style={baseStyles.container}>
          <Section style={baseStyles.header}>
            <Img
              src={brand.wordmarkUrl || `${baseUrl}${LINGXI_BRAND_ASSETS.wordmarkOnLight}`}
              alt={brand.name}
              {...(hasCustomLogo ? CUSTOM_LOGO_SIZE : WORDMARK_SIZE)}
              style={hasCustomLogo ? { display: 'block', width: 'auto' } : { display: 'block' }}
            />
          </Section>

          <Section style={baseStyles.content}>{children}</Section>
        </Container>

        {!hideFooter && <EmailFooter baseUrl={baseUrl} showUnsubscribe={showUnsubscribe} />}
      </Body>
    </Html>
  )
}

export default EmailLayout
