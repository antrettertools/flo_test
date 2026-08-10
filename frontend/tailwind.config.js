/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      // kept in sync with src/styles/tokens.ts colors
      colors: {
        c3: {
          text: '#33302F',
          greydark: '#5e5a58',
          grey: '#bdb2aa',
          greylight: '#d9d8cd',
          white: '#ffffff',
          bluegreen: '#4ab79f',
          blue: '#4597bf',
          bluedark: '#407188',
          bluelight: '#93d2e1',
          green: '#3e7263',
          greendark: '#205959',
          greenlight: '#89a767',
          red: '#c04343',
          orange: '#e18e2a',
          yellow: '#f8c36e',
          yellowgreen: '#b1b52e',
          yellowlight: '#fef4dc',
        },
      },
      fontFamily: {
        heading: ['Jost', 'Lato', 'Arial', 'sans-serif'],
        body: ['Lato', 'Arial', 'sans-serif'],
      },
    },
  },
  plugins: [],
};
