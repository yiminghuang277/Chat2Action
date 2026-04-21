/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#0f172a",
        mist: "#f5f7fb",
        line: "#d9e2f1",
        brand: "#14532d",
        accent: "#0f766e",
        warn: "#9a3412"
      },
      boxShadow: {
        panel: "0 16px 50px rgba(15, 23, 42, 0.08)"
      }
    }
  },
  plugins: []
};
