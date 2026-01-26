/**
 * EspressoBot Design Tokens
 *
 * Centralized design system constants for consistent styling across the app.
 * Import these in components to ensure visual consistency.
 */

// =============================================================================
// COLOR PALETTE
// =============================================================================

export const colors = {
  // Neutral (Zinc) - Primary UI colors
  neutral: {
    50: '#fafafa',
    100: '#f4f4f5',
    200: '#e4e4e7',
    300: '#d4d4d8',
    400: '#a1a1aa',
    500: '#71717a',
    600: '#52525b',
    700: '#3f3f46',
    800: '#27272a',
    900: '#18181b',
    950: '#09090b',
  },

  // Brand (Amber) - Primary brand color
  brand: {
    50: '#fffbeb',
    100: '#fef3c7',
    200: '#fde68a',
    300: '#fcd34d',
    400: '#fbbf24',
    500: '#f59e0b',
    600: '#d97706',
    700: '#b45309',
    800: '#92400e',
    900: '#78350f',
    950: '#451a03',
  },

  // Accent (Blue) - Interactive elements, links
  accent: {
    50: '#eff6ff',
    100: '#dbeafe',
    200: '#bfdbfe',
    300: '#93c5fd',
    400: '#60a5fa',
    500: '#3b82f6',
    600: '#2563eb',
    700: '#1d4ed8',
    800: '#1e40af',
    900: '#1e3a8a',
  },

  // Reasoning (Purple) - AI reasoning/thinking displays
  reasoning: {
    50: '#faf5ff',
    100: '#f3e8ff',
    200: '#e9d5ff',
    300: '#d8b4fe',
    400: '#c084fc',
    500: '#a855f7',
    600: '#9333ea',
    700: '#7c3aed',
    800: '#6b21a8',
    900: '#581c87',
  },

  // Semantic colors
  success: {
    light: '#10b981',
    dark: '#34d399',
  },
  warning: {
    light: '#f59e0b',
    dark: '#fbbf24',
  },
  error: {
    light: '#ef4444',
    dark: '#f87171',
  },
  info: {
    light: '#3b82f6',
    dark: '#60a5fa',
  },
} as const;

// =============================================================================
// TYPOGRAPHY
// =============================================================================

export const typography = {
  // Font family
  fontFamily: {
    sans: "'Inter Variable', 'Inter', ui-sans-serif, system-ui, sans-serif",
    mono: "'Monaco', 'Menlo', 'Ubuntu Mono', 'Consolas', 'source-code-pro', monospace",
  },

  // Heading scale
  heading: {
    h1: 'text-3xl font-bold tracking-tight', // Page titles
    h2: 'text-2xl font-semibold tracking-tight', // Section titles
    h3: 'text-xl font-semibold', // Card titles
    h4: 'text-lg font-medium', // Subsections
    h5: 'text-base font-medium', // Labels
    h6: 'text-sm font-medium', // Small labels
  },

  // Body text
  body: {
    large: 'text-lg leading-relaxed',
    default: 'text-base leading-relaxed',
    small: 'text-sm leading-relaxed',
    tiny: 'text-xs leading-relaxed',
  },

  // Special text styles
  label: 'text-sm font-medium text-zinc-700 dark:text-zinc-300',
  helper: 'text-xs text-zinc-500 dark:text-zinc-400',
  error: 'text-xs text-red-600 dark:text-red-400',
} as const;

// =============================================================================
// SPACING
// =============================================================================

export const spacing = {
  // Container padding (responsive)
  container: {
    x: 'px-4 md:px-6 lg:px-8',
    y: 'py-4 md:py-6 lg:py-8',
    all: 'p-4 md:p-6 lg:p-8',
  },

  // Card padding
  card: {
    sm: 'p-3 md:p-4',
    default: 'p-4 md:p-6',
    lg: 'p-6 md:p-8',
  },

  // Section gaps
  section: {
    sm: 'gap-4',
    default: 'gap-6 md:gap-8',
    lg: 'gap-8 md:gap-12',
  },

  // Form field gaps
  form: {
    field: 'gap-4',
    label: 'gap-1.5',
    group: 'gap-6',
  },

  // Stack (vertical) spacing
  stack: {
    xs: 'space-y-1',
    sm: 'space-y-2',
    default: 'space-y-4',
    lg: 'space-y-6',
    xl: 'space-y-8',
  },
} as const;

// =============================================================================
// BORDERS & RADIUS
// =============================================================================

export const borders = {
  // Border radius
  radius: {
    sm: 'rounded-md',      // 0.375rem - Small elements (badges, chips)
    default: 'rounded-lg', // 0.5rem - Cards, inputs
    lg: 'rounded-xl',      // 0.75rem - Larger cards, modals
    xl: 'rounded-2xl',     // 1rem - Feature cards
    '2xl': 'rounded-3xl',  // 1.5rem - Hero sections
    full: 'rounded-full',  // Pills, avatars
  },

  // Border colors (use with border-*)
  color: {
    light: 'border-zinc-200/70',
    dark: 'dark:border-zinc-800/70',
    subtle: 'border-zinc-200/40 dark:border-zinc-800/40',
    strong: 'border-zinc-300 dark:border-zinc-700',
    glass: 'border-white/20 dark:border-white/10',
  },
} as const;

// =============================================================================
// SHADOWS
// =============================================================================

export const shadows = {
  // Elevation levels
  none: 'shadow-none',
  xs: 'shadow-xs',
  sm: 'shadow-sm',
  default: 'shadow-md',
  lg: 'shadow-lg',
  xl: 'shadow-xl',
  '2xl': 'shadow-2xl',

  // Colored shadows (for premium effects)
  brand: 'shadow-lg shadow-amber-500/20 dark:shadow-amber-500/10',
  accent: 'shadow-lg shadow-blue-500/20 dark:shadow-blue-500/10',
  dark: 'shadow-lg shadow-zinc-900/10 dark:shadow-black/40',
} as const;

// =============================================================================
// GLASS MORPHISM
// =============================================================================

export const glass = {
  // Light mode glass effects
  light: {
    subtle: 'bg-white/70 backdrop-blur-md border border-white/10',
    default: 'bg-white/85 backdrop-blur-xl border border-white/20',
    strong: 'bg-white/90 backdrop-blur-2xl border border-white/30',
  },

  // Dark mode glass effects
  dark: {
    subtle: 'dark:bg-zinc-900/70 dark:backdrop-blur-md dark:border-white/5',
    default: 'dark:bg-zinc-900/85 dark:backdrop-blur-xl dark:border-white/10',
    strong: 'dark:bg-zinc-900/90 dark:backdrop-blur-2xl dark:border-white/15',
  },

  // Combined (use directly)
  card: 'bg-white/80 backdrop-blur-md border border-zinc-200/30 shadow-sm dark:bg-zinc-900/80 dark:border-zinc-800/30',
  sidebar: 'bg-white/60 backdrop-blur-lg border-r border-zinc-200/40 dark:bg-zinc-950/60 dark:border-zinc-800/40',
  topbar: 'bg-white/70 backdrop-blur-xl border-b border-zinc-200/50 shadow-sm dark:bg-zinc-900/70 dark:border-zinc-800/50',
  modal: 'bg-white/95 backdrop-blur-2xl border border-zinc-200/50 shadow-2xl dark:bg-zinc-900/95 dark:border-zinc-800/50',
} as const;

// =============================================================================
// TRANSITIONS & ANIMATIONS
// =============================================================================

export const transitions = {
  // Duration
  duration: {
    fast: 'duration-100',
    default: 'duration-150',
    medium: 'duration-200',
    slow: 'duration-300',
  },

  // Easing
  ease: {
    default: 'ease-out',
    in: 'ease-in',
    inOut: 'ease-in-out',
    bounce: 'cubic-bezier(0.68, -0.55, 0.265, 1.55)',
  },

  // Common transitions
  colors: 'transition-colors duration-150 ease-out',
  transform: 'transition-transform duration-200 ease-out',
  all: 'transition-all duration-200 ease-out',
  opacity: 'transition-opacity duration-150 ease-out',
} as const;

export const animations = {
  // Entrance animations
  fadeIn: 'animate-fade-in',
  slideInBottom: 'animate-slide-in-bottom',
  slideInRight: 'animate-slide-in-right',
  slideInLeft: 'animate-slide-in-left',
  scaleIn: 'animate-scale-in',

  // Continuous animations
  pulse: 'animate-pulse',
  spin: 'animate-spin',
  shimmer: 'animate-shimmer',
  breathe: 'animate-breathe',
  gentleBounce: 'animate-gentle-bounce',

  // Delays (for staggered animations)
  delay: {
    75: 'animation-delay-75',
    100: 'animation-delay-100',
    150: 'animation-delay-150',
    200: 'animation-delay-200',
    300: 'animation-delay-300',
    400: 'animation-delay-400',
    500: 'animation-delay-500',
  },
} as const;

// =============================================================================
// COMPONENT PRESETS
// =============================================================================

export const presets = {
  // Card presets
  card: {
    default: `${borders.radius.lg} ${glass.card} ${shadows.sm}`,
    elevated: `${borders.radius.xl} ${glass.card} ${shadows.lg}`,
    interactive: `${borders.radius.lg} ${glass.card} ${shadows.sm} ${transitions.all} hover:shadow-md hover:-translate-y-0.5`,
  },

  // Button presets (use with Catalyst Button when possible)
  button: {
    primary: 'bg-zinc-900 dark:bg-zinc-100 text-white dark:text-zinc-900 hover:bg-zinc-800 dark:hover:bg-zinc-200 shadow-lg hover:shadow-xl transition-all duration-200',
    secondary: 'bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 border border-zinc-200 dark:border-zinc-700 hover:bg-zinc-50 dark:hover:bg-zinc-700 shadow-sm hover:shadow transition-all duration-200',
    ghost: 'text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800 hover:text-zinc-900 dark:hover:text-zinc-100 transition-colors duration-150',
    danger: 'bg-red-600 dark:bg-red-500 text-white hover:bg-red-700 dark:hover:bg-red-600 shadow-lg shadow-red-500/25 hover:shadow-xl transition-all duration-200',
    brand: 'bg-gradient-to-r from-zinc-900 via-amber-950 to-zinc-900 text-white hover:from-amber-950 hover:via-amber-900 hover:to-amber-950 shadow-xl shadow-zinc-900/25 hover:shadow-2xl transition-all duration-300',
  },

  // Input presets (complement Catalyst Input)
  input: {
    default: 'w-full rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2 text-sm placeholder:text-zinc-500 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20 transition-all duration-150',
  },

  // Focus ring
  focus: 'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 focus:ring-offset-white dark:focus:ring-offset-zinc-900',
} as const;

// =============================================================================
// BREAKPOINTS (for reference - Tailwind handles these)
// =============================================================================

export const breakpoints = {
  sm: '640px',
  md: '768px',
  lg: '1024px',
  xl: '1280px',
  '2xl': '1536px',
} as const;

// =============================================================================
// Z-INDEX LAYERS
// =============================================================================

export const zIndex = {
  base: 0,
  dropdown: 10,
  sticky: 20,
  fixed: 30,
  modalBackdrop: 40,
  modal: 50,
  popover: 60,
  tooltip: 70,
  toast: 80,
} as const;
