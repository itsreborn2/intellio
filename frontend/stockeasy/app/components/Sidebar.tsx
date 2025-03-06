'use client'

import { Suspense } from 'react'
import { Button } from "intellio-common/components/ui/button"
import {
  Home,
  BarChart,
  ChartColumn,
  FileStack,
  FileText,
  User,
  Users,
  Settings,
  LayoutDashboard // 로고 대신 LayoutDashboard 아이콘 사용 (V와 유사)
} from 'lucide-react';

// 컨텐츠 컴포넌트
function SidebarContent() {
  return (
    <div className="w-[59px] border-r bg-gray-200 flex flex-col h-full">
      <div className="min-h-0 overflow-y-auto">
        <div className="pt-6">
          <div className="space-y-6 w-full flex flex-col items-center">
            <button className="sidebar-button">
              <Home className="icon" />
            </button>
            <button className="sidebar-button">
              <ChartColumn className="icon" />
            </button>
            <button className="sidebar-button">
              <FileStack className="icon" />
            </button>
            <button className="sidebar-button">
              <User className="icon" />
            </button>
            <button className="sidebar-button">
              <Settings className="icon" />
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

// 메인 컴포넌트
export default function Sidebar() {
  return (
    <Suspense fallback={<div className="w-[59px] bg-background border-r animate-pulse">
      <div className="p-4">
        <div className="h-6 bg-gray-200 rounded w-3/4"></div>
      </div>
      <div className="p-2">
        <div className="space-y-2">
          <div className="h-4 bg-gray-200 rounded w-1/2"></div>
          <div className="h-4 bg-gray-200 rounded w-2/3"></div>
        </div>
      </div>
    </div>}>
      <SidebarContent />
    </Suspense>
  )
}
