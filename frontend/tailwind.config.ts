import type { Config } from 'tailwindcss'

const config: Config = {
  content: ['./src/**/*.{js,ts,jsx,tsx,mdx}'],
  theme: {
    extend: {
      colors: {
        pro: '#10b981',
        con: '#f43f5e',
      },
    },
  },
  plugins: [],
}

export default config
