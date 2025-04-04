import type { Config } from "tailwindcss";
// common의 설정을 가져옵니다
import commonConfig from '../common/tailwind.config';

const config: Config = {
  darkMode: "class",
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./templates/**/*.{js,ts,jsx,tsx,mdx}",
    "../common/components/**/*.{js,ts,jsx,tsx,mdx}",  // common 컴포넌트 포함
  ],
  // common의 설정을 presets로 사용
  presets: [commonConfig as Partial<Config>],
  theme: {
    extend: {
      // Roboto 폰트 설정 추가
      fontFamily: {
        sans: ['Roboto', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Helvetica Neue', 'Arial', 'sans-serif'],
      },
      fontSize: {
        // ChatGPT 스타일 폰트 크기 설정
        'xs': '0.75rem',     // 12px
        'sm': '0.875rem',    // 14px
        'base': '1rem',      // 16px (기본)
        'lg': '1.125rem',    // 18px
        'xl': '1.25rem',     // 20px
        '2xl': '1.5rem',     // 24px
        '3xl': '1.875rem',   // 30px
        '4xl': '2.25rem',    // 36px
      },
      lineHeight: {
        // ChatGPT 스타일 줄 간격 설정
        'tight': '1.25',
        'normal': '1.5',
        'relaxed': '1.625',
      }
    }
  },
  plugins: [require("tailwindcss-animate")],
};

export default config;
