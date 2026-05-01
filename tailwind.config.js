/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./templates/**/*.html",
    "./static/js/**/*.js",
    "./*.py"
  ],
  safelist: [
    "text-red-400",
    "text-yellow-400",
    "text-green-400",
    "drop-shadow-[0_0_8px_rgba(248,113,113,0.4)]",
    "drop-shadow-[0_0_8px_rgba(250,204,21,0.3)]",
    "drop-shadow-[0_0_10px_rgba(74,222,128,0.3)]"
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Montserrat", "sans-serif"],
      }
    },
  },
  plugins: [],
}

