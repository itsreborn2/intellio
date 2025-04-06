'use client'

import { ReactNode } from 'react'
import { Toaster } from 'sonner'

type InternalTestLayoutProps = {
  children: ReactNode
}

export default function InternalTestLayout({ children }: InternalTestLayoutProps) {
  return (
    <div className="flex min-h-screen flex-col">
      <div className="bg-blue-200 text-white shadow-md">
        <h1 className="text-xl font-bold">스톡이지 내부 테스트 페이지</h1>
        <p className="text-sm opacity-80">개발용 페이지입니다. 외부에 공개하지 마세요.</p>
      </div>
      
      <div className="flex-1 container mx-auto py-6">
        {children}
      </div>
      
      <footer className="bg-gray-300 py-3 text-center text-sm text-gray-500">
        <p>© {new Date().getFullYear()} Intellio - 내부용</p>
      </footer>
      
      <Toaster />
    </div>
  )
} 