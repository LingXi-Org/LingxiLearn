import {
  buildUnifiedSettingsNavigation,
  SETTINGS_NAVIGATION_BILLING_ENABLED,
  type UnifiedNavigationSection,
  type UnifiedSettingsNavigationItem,
  type UnifiedSettingsSection,
} from '@/components/settings/navigation'

export type SettingsSection = UnifiedSettingsSection

export type NavigationSection = UnifiedNavigationSection

export type NavigationItem = UnifiedSettingsNavigationItem

export const isBillingEnabled = SETTINGS_NAVIGATION_BILLING_ENABLED

export const sectionConfig: { key: NavigationSection; title: string }[] = [
  { key: 'account', title: '账户' },
  { key: 'workspace', title: '工作区' },
  { key: 'organization', title: '组织' },
  { key: 'platform', title: '平台' },
]

export const allNavigationItems: NavigationItem[] = buildUnifiedSettingsNavigation()

/**
 * Title + description for a settings section, the single source of truth used by
 * `SettingsPanel` to render the page header. Falls back to `null` for sections
 * that are gated off (callers render no title in that case).
 */
export function getSettingsSectionMeta(
  section: SettingsSection
): { label: string; description: string; docsLink?: string } | null {
  const item = allNavigationItems.find((navItem) => navItem.id === section)
  return item
    ? {
        label: item.label,
        description: item.description,
        docsLink: item.docsLink,
      }
    : null
}
