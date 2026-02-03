/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#f0f5ff',
          100: '#e0ebff',
          200: '#c2d6ff',
          300: '#94b8ff',
          400: '#6090ff',
          500: '#3b6bff',
          600: '#1e4aff',
          700: '#1a3de0',
          800: '#1a35b5',
          900: '#1b318f',
        },
      },
    },
  },
  plugins: [],
}
