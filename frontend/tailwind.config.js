/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        brand: {
          primary: 'var(--brand-primary)',
          'primary-light': 'var(--brand-primary-light)',
          'primary-dark': 'var(--brand-primary-dark)',
        },
        bg: {
          page: 'var(--bg-page)',
          surface: 'var(--bg-surface)',
          'surface-hover': 'var(--bg-surface-hover)',
          'surface-elevated': 'var(--bg-surface-elevated)',
          glass: 'var(--bg-glass)',
          sidebar: 'var(--bg-sidebar)',
          'sidebar-hover': 'var(--bg-sidebar-hover)',
          'sidebar-active': 'var(--bg-sidebar-active)',
        },
        text: {
          primary: 'var(--text-primary)',
          secondary: 'var(--text-secondary)',
          muted: 'var(--text-muted)',
          'on-dark': 'var(--text-on-dark)',
          'on-dark-muted': 'var(--text-on-dark-muted)',
        },
        border: {
          light: 'var(--border-light)',
          medium: 'var(--border-medium)',
          focus: 'var(--border-focus)',
        },
        status: {
          available: 'var(--status-available)',
          'available-bg': 'var(--status-available-bg)',
          occupied: 'var(--status-occupied)',
          'occupied-bg': 'var(--status-occupied-bg)',
          cleaning: 'var(--status-cleaning)',
          'cleaning-bg': 'var(--status-cleaning-bg)',
          waiting: 'var(--status-waiting)',
          'waiting-bg': 'var(--status-waiting-bg)',
          admitted: 'var(--status-admitted)',
          'admitted-bg': 'var(--status-admitted-bg)',
          discharged: 'var(--status-discharged)',
          'discharged-bg': 'var(--status-discharged-bg)',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'Cascadia Code', 'Fira Code', 'monospace'],
      },
      boxShadow: {
        xs: 'var(--shadow-xs)',
        card: 'var(--shadow-card)',
        md: 'var(--shadow-md)',
        lg: 'var(--shadow-lg)',
        modal: 'var(--shadow-modal)',
        glow: 'var(--shadow-glow)',
      },
      borderRadius: {
        sm: 'var(--radius-sm)',
        md: 'var(--radius-md)',
        lg: 'var(--radius-lg)',
        xl: 'var(--radius-xl)',
      },
      animation: {
        'fade-in': 'fade-in 0.3s ease-out both',
        'slide-in': 'slide-in-right 0.3s ease-out both',
        'slide-up': 'slide-in-up 0.25s ease-out both',
        'scale-in': 'scale-in 0.2s ease-out both',
        'pulse-soft': 'pulse-soft 2s ease-in-out infinite',
        'shimmer': 'shimmer 1.5s ease-in-out infinite',
        'spin-slow': 'spin-slow 3s linear infinite',
      },
      keyframes: {
        'fade-in': {
          from: { opacity: '0', transform: 'translateY(4px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        'slide-in-right': {
          from: { opacity: '0', transform: 'translateX(16px)' },
          to: { opacity: '1', transform: 'translateX(0)' },
        },
        'slide-in-up': {
          from: { opacity: '0', transform: 'translateY(8px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        'scale-in': {
          from: { opacity: '0', transform: 'scale(0.95)' },
          to: { opacity: '1', transform: 'scale(1)' },
        },
        'pulse-soft': {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.6' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
        'spin-slow': {
          from: { transform: 'rotate(0deg)' },
          to: { transform: 'rotate(360deg)' },
        },
      },
    },
  },
  plugins: [],
}
