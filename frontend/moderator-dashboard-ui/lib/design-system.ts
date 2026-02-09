/**
 * Design System Constants для B2B Platform - Moderator Dashboard
 * 
 * Централизованная система дизайна для обеспечения консистентности UI
 */

// Color Palette - B2B Admin Theme
export const colors = {
  // Primary Brand Colors
  primary: {
    50: '#EEF2FF',
    100: '#E0E7FF',
    200: '#C7D2FE',
    300: '#A5B4FC',
    400: '#818CF8',
    500: '#6366F1', // Main brand color
    600: '#4F46E5',
    700: '#4338CA',
    800: '#3730A3',
    900: '#312E81',
  },
  
  // Semantic Colors
  success: {
    50: '#ECFDF5',
    100: '#D1FAE5',
    500: '#10B981',
    600: '#059669',
    700: '#047857',
  },
  
  warning: {
    50: '#FFFBEB',
    100: '#FEF3C7',
    500: '#F59E0B',
    600: '#D97706',
    700: '#B45309',
  },
  
  danger: {
    50: '#FEF2F2',
    100: '#FEE2E2',
    500: '#EF4444',
    600: '#DC2626',
    700: '#B91C1C',
  },
  
  // Neutral Colors
  neutral: {
    50: '#F9FAFB',
    100: '#F3F4F6',
    200: '#E5E7EB',
    300: '#D1D5DB',
    400: '#9CA3AF',
    500: '#6B7280',
    600: '#4B5563',
    700: '#374151',
    800: '#1F2937',
    900: '#111827',
  },
  
  // Info Colors
  info: {
    50: '#EFF6FF',
    100: '#DBEAFE',
    500: '#3B82F6',
    600: '#2563EB',
    700: '#1D4ED8',
  },
} as const

// Typography System
export const typography = {
  fontFamily: {
    sans: 'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
    mono: '"JetBrains Mono", "Fira Code", Consolas, monospace',
  },
  
  fontSize: {
    xs: '0.75rem',      // 12px
    sm: '0.875rem',     // 14px
    base: '1rem',       // 16px
    lg: '1.125rem',     // 18px
    xl: '1.25rem',      // 20px
    '2xl': '1.5rem',    // 24px
    '3xl': '1.875rem',  // 30px
    '4xl': '2.25rem',   // 36px
    '5xl': '3rem',      // 48px
  },
  
  fontWeight: {
    normal: 400,
    medium: 500,
    semibold: 600,
    bold: 700,
  },
  
  lineHeight: {
    tight: 1.25,
    normal: 1.5,
    relaxed: 1.75,
  },
} as const

// Spacing System (8px grid)
export const spacing = {
  0: '0',
  1: '0.25rem',   // 4px
  2: '0.5rem',    // 8px
  3: '0.75rem',   // 12px
  4: '1rem',      // 16px
  5: '1.25rem',   // 20px
  6: '1.5rem',    // 24px
  8: '2rem',      // 32px
  10: '2.5rem',   // 40px
  12: '3rem',     // 48px
  16: '4rem',     // 64px
  20: '5rem',     // 80px
  24: '6rem',     // 96px
} as const

// Border Radius
export const borderRadius = {
  none: '0',
  sm: '0.25rem',   // 4px - inputs
  md: '0.5rem',    // 8px - cards
  lg: '0.75rem',   // 12px
  xl: '1rem',      // 16px
  full: '9999px',  // pills, avatars
} as const

// Shadows
export const shadows = {
  sm: '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
  base: '0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06)',
  md: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
  lg: '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)',
  xl: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)',
} as const

// Z-Index Scale
export const zIndex = {
  base: 0,
  dropdown: 1000,
  sticky: 1100,
  fixed: 1200,
  modalBackdrop: 1300,
  modal: 1400,
  popover: 1500,
  tooltip: 1600,
} as const

// Breakpoints (Desktop-first approach)
export const breakpoints = {
  xs: '480px',
  sm: '640px',
  md: '768px',
  lg: '1024px',
  xl: '1280px',
  '2xl': '1536px',
} as const

// Animation Durations
export const animation = {
  fast: '150ms',
  base: '200ms',
  slow: '300ms',
  slower: '500ms',
} as const

// Component-specific constants
export const components = {
  // Card
  card: {
    padding: spacing[6],
    borderRadius: borderRadius.md,
    shadow: shadows.base,
  },
  
  // Button
  button: {
    height: {
      sm: '2rem',      // 32px
      md: '2.5rem',    // 40px
      lg: '3rem',      // 48px
    },
    padding: {
      sm: `${spacing[2]} ${spacing[3]}`,
      md: `${spacing[3]} ${spacing[4]}`,
      lg: `${spacing[4]} ${spacing[6]}`,
    },
  },
  
  // Input
  input: {
    height: '2.5rem',  // 40px
    borderRadius: borderRadius.sm,
    padding: `${spacing[2]} ${spacing[3]}`,
  },
  
  // Table
  table: {
    rowHeight: '3.5rem',  // 56px
    headerHeight: '3rem', // 48px
  },
} as const

// Risk Score Colors
export const riskColors = {
  low: colors.success[500],      // 0-30
  moderate: colors.warning[500], // 31-60
  high: colors.danger[500],      // 61-100
} as const

// Status Colors
export const statusColors = {
  active: colors.success[500],
  inactive: colors.neutral[400],
  pending: colors.warning[500],
  blocked: colors.danger[500],
  completed: colors.success[500],
  running: colors.info[500],
  error: colors.danger[500],
} as const

// Helper function to get risk color based on score
export function getRiskColor(score: number): string {
  if (score <= 30) return riskColors.low
  if (score <= 60) return riskColors.moderate
  return riskColors.high
}

// Helper function to get risk label
export function getRiskLabel(score: number): string {
  if (score <= 30) return 'Низкий риск'
  if (score <= 60) return 'Средний риск'
  return 'Высокий риск'
}

// Helper function to get status color
export function getStatusColor(status: string): string {
  return statusColors[status as keyof typeof statusColors] || colors.neutral[400]
}
