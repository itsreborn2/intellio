'use client'

import './globals.css';
import AIChatArea from './components/AIChatArea';


export default function StockEasyLandingPage() {
  return (
    <div className="flex-1 p-0 sm:p-2 md:p-4 overflow-auto w-full">
      <div className="w-full max-w-[1280px] mx-auto px-0 sm:px-2">
        <AIChatArea />
      </div>
    </div>
  );
}
