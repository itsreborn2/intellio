import type { Config } from "tailwindcss";
// common의 설정을 가져옵니다
import commonConfig from '../common/tailwind.config';

const config: Config = {
  darkMode: ["class"],
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./templates/**/*.{js,ts,jsx,tsx,mdx}",
    "../common/components/**/*.{js,ts,jsx,tsx,mdx}",  // common 컴포넌트 포함
  ],
  // common의 설정을 presets로 사용
  presets: [commonConfig],
  theme: {
    extend: {
      // 프로젝트 특정 추가 설정이 필요한 경우 여기에 작성
    }
  },
  plugins: [require("tailwindcss-animate")],
};

export default config;
