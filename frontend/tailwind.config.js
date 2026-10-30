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
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      boxShadow: {
        card: 'var(--shadow-card)',
        modal: 'var(--shadow-modal)',
      },
      borderRadius: {
        sm: 'var(--radius-sm)',
        md: 'var(--radius-md)',
        lg: 'var(--radius-lg)',
      },
    },
  },
  plugins: [],
}
