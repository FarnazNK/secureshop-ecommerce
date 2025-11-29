import type { Config } from 'tailwindcss';

const config: Config = {
  darkMode: ['class'],
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      // Distinctive color palette - warm neutrals with terracotta accent
      colors: {
        // Primary brand colors - warm terracotta
        primary: {
          50: '#fef7f4',
          100: '#fdeee7',
          200: '#fbd9ca',
          300: '#f7b99e',
          400: '#f1906a',
          500: '#e86f42', // Main brand color
          600: '#d45428',
          700: '#b04221',
          800: '#8f3720',
          900: '#75301e',
          950: '#3f160c',
        },
        // Warm neutrals for backgrounds
        sand: {
          50: '#fdfcfb',
          100: '#f9f7f4',
          200: '#f3efe9',
          300: '#e8e2d9',
          400: '#d4cbc0',
          500: '#b8aa99',
          600: '#9a8976',
          700: '#7d6d5c',
          800: '#675a4d',
          900: '#574c42',
          950: '#2d2722',
        },
        // Deep charcoal for text
        ink: {
          50: '#f6f6f6',
          100: '#e7e7e7',
          200: '#d1d1d1',
          300: '#b0b0b0',
          400: '#888888',
          500: '#6d6d6d',
          600: '#5d5d5d',
          700: '#4f4f4f',
          800: '#454545',
          900: '#262626', // Main text color
          950: '#171717',
        },
        // Accent colors
        sage: {
          400: '#8faa8f',
          500: '#6b8b6b',
          600: '#547654',
        },
        ocean: {
          400: '#6b99aa',
          500: '#4a7d91',
          600: '#3a6677',
        },
      },
      // Distinctive typography
      fontFamily: {
        // Editorial serif for headings
        display: ['Playfair Display', 'Georgia', 'serif'],
        // Clean sans for body
        body: ['DM Sans', 'system-ui', 'sans-serif'],
        // Monospace for prices/codes
        mono: ['JetBrains Mono', 'Consolas', 'monospace'],
      },
      fontSize: {
        'display-xl': ['4.5rem', { lineHeight: '1', letterSpacing: '-0.02em' }],
        'display-lg': ['3.5rem', { lineHeight: '1.1', letterSpacing: '-0.02em' }],
        'display-md': ['2.5rem', { lineHeight: '1.2', letterSpacing: '-0.01em' }],
        'display-sm': ['1.875rem', { lineHeight: '1.3' }],
        'body-xl': ['1.25rem', { lineHeight: '1.6' }],
        'body-lg': ['1.125rem', { lineHeight: '1.6' }],
        'body-md': ['1rem', { lineHeight: '1.6' }],
        'body-sm': ['0.875rem', { lineHeight: '1.5' }],
        'body-xs': ['0.75rem', { lineHeight: '1.5' }],
      },
      // Generous spacing for luxury feel
      spacing: {
        '18': '4.5rem',
        '22': '5.5rem',
        '30': '7.5rem',
        '34': '8.5rem',
        '38': '9.5rem',
      },
      // Refined border radius
      borderRadius: {
        'soft': '0.375rem',
        'card': '0.75rem',
        'xl': '1rem',
        '2xl': '1.5rem',
      },
      // Subtle shadows
      boxShadow: {
        'soft': '0 2px 8px -2px rgba(38, 38, 38, 0.08)',
        'medium': '0 4px 16px -4px rgba(38, 38, 38, 0.12)',
        'elevated': '0 8px 32px -8px rgba(38, 38, 38, 0.16)',
        'card': '0 1px 3px rgba(38, 38, 38, 0.04), 0 4px 12px rgba(38, 38, 38, 0.06)',
        'card-hover': '0 4px 8px rgba(38, 38, 38, 0.06), 0 12px 24px rgba(38, 38, 38, 0.1)',
      },
      // Smooth animations
      animation: {
        'fade-in': 'fadeIn 0.5s ease-out',
        'slide-up': 'slideUp 0.5s ease-out',
        'slide-down': 'slideDown 0.3s ease-out',
        'scale-in': 'scaleIn 0.2s ease-out',
        'shimmer': 'shimmer 2s infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(16px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        slideDown: {
          '0%': { opacity: '0', transform: 'translateY(-8px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        scaleIn: {
          '0%': { opacity: '0', transform: 'scale(0.95)' },
          '100%': { opacity: '1', transform: 'scale(1)' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
      },
      // Grid template for product layouts
      gridTemplateColumns: {
        'products': 'repeat(auto-fill, minmax(280px, 1fr))',
        'products-lg': 'repeat(auto-fill, minmax(320px, 1fr))',
      },
      // Aspect ratios
      aspectRatio: {
        'product': '4 / 5',
        'hero': '16 / 9',
        'square': '1 / 1',
      },
      // Background patterns
      backgroundImage: {
        'grain': "url(\"data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.65' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)'/%3E%3C/svg%3E\")",
        'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
      },
    },
  },
  plugins: [],
};

export default config;
