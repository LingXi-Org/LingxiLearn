import { cn } from '@sim/emcn'
import { Cta } from '@/app/(landing)/components/cta/cta'
import { Features } from '@/app/(landing)/components/features'
import { Hero } from '@/app/(landing)/components/hero'
import { HomeStructuredData } from '@/app/(landing)/components/home-structured-data'
import { LANDING_SECTION_RHYTHM } from '@/app/(landing)/components/landing-layout'
import { Mothership } from '@/app/(landing)/components/mothership/mothership'
import { ProductDemo } from '@/app/(landing)/components/product-demo'
import { LandingAnalytics } from '@/app/(landing)/landing-analytics'

/**
 * Landing page root - owns the section order and the `<main>` content region.
 *
 * The shared chrome (`light` + brand token layer, scroll port, skip link, navbar
 * with build/revalidate-time GitHub stars, footer, and site-wide JSON-LD) is
 * owned by the route-group layout via `LandingShell`, so the landing family can
 * never drift and the navbar persists across navigation. This page emits only
 * its `<main>` and the home-specific structured data.
 *
 * `<main>` is a `flex flex-col` whose `gap` is the single source of truth for
 * inter-section rhythm - sections carry no vertical margin/padding of their own,
 * so one knob keeps every section break uniform across the page. Each section
 * component owns its own landmark (`<section id aria-labelledby>`).
 */
export default function Landing() {
  return (
    <main id='main-content' className={cn('flex flex-col', LANDING_SECTION_RHYTHM)}>
      <LandingAnalytics />
      <HomeStructuredData />
      <Hero />
      <ProductDemo />
      <Mothership />
      <Features />
      <Cta />
    </main>
  )
}
