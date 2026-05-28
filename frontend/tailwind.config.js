/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        // Si quieres asegurar tu fuente monoespaciada:
        mono: ['JetBrains Mono', 'monospace'],
        // Puedes crear una clase para tus títulos y borrar el style={{fontFamily: 'Syne'}} de tu JSX
        syne: ['Syne', 'sans-serif']
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
