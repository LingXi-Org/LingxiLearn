/**
 * Keep the workspace build independent of Google Fonts availability. The
 * previous next/font/google call made static Docker builds fail whenever
 * fonts.gstatic.com was unreachable; this variable lets the existing CSS
 * fallback stack provide the same local-first system font behavior.
 */
export const inter = { variable: '--font-inter' } as const
