// 'use client' 지시문 추가 (window.location 사용을 위해)
'use client'

import Link from 'next/link'

export default function Home() {
  // 페이지 이동 함수
  const handleNavigate = (url: string) => {
    window.location.href = url;
  };

  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-gradient-to-b from-gray-50 to-gray-100">
      <div className="text-center space-y-12">
        {/* 제목 섹션 */}
        <div className="space-y-4">
          <h1 className="text-5xl font-bold">
            <span className="bg-gradient-to-r from-blue-600 to-green-600 bg-clip-text text-transparent">
              Welcome to Intellio
            </span>
          </h1>
          <p className="text-xl text-gray-600">Choose your service to get started</p>
        </div>
        
        {/* 버튼 섹션 */}
        <div className="flex gap-6">
          {/* DocEasy 버튼 */}
          <button
            onClick={() => handleNavigate('http://localhost:3010')}
            className="custom-button button-glow bg-gradient-to-r from-blue-600 to-blue-800 
                     hover:from-blue-700 hover:to-blue-900 hover:shadow-[0_0_20px_rgba(37,99,235,0.4)]
                     focus:ring-blue-500"
          >
            <span className="flex items-center gap-2">
              <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} 
                      d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              DocEasy
            </span>
          </button>
          
          {/* StockEasy 버튼 */}
          <button
            onClick={() => handleNavigate('http://localhost:3020')}
            className="custom-button button-glow bg-gradient-to-r from-emerald-600 to-green-700
                     hover:from-emerald-700 hover:to-green-800 hover:shadow-[0_0_20px_rgba(16,185,129,0.4)]
                     focus:ring-green-500"
          >
            <span className="flex items-center gap-2">
              <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} 
                      d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
              </svg>
              StockEasy
            </span>
          </button>
        </div>
      </div>
    </div>
  )
}
