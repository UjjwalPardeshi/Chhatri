/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        navy: '#0f1a33',
        ink: '#0f172a',
        primary: '#0b63c9',
        accent: '#38a3e8',
        paper: '#f3f5f8',
        amber: '#e39a4f',
        red: '#b91c1c',
        green: '#15803d',
      },
      fontFamily: {
        ubuntu: ['Ubuntu', 'sans-serif'],
        devanagari: ['Noto Sans Devanagari', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
