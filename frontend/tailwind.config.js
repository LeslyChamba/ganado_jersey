/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      fontFamily: {
        display: ['Syne', 'sans-serif'],
        body:    ['Lora', 'serif'],
        mono:    ['JetBrains Mono', 'monospace'],
      },
      colors: {
        earth:  '#2C1810',
        clay:   '#8B4513',
        hay:    '#D4A853',
        cream:  '#F5EDD8',
        sage:   '#6B8F71',
        'sage-light': '#A8C5AD',
        dark:   '#1A1008',
        accent: '#E07B39',
      },
    },
  },
  plugins: [],
}
