import { CheckCircle2, Clock, AlertCircle } from "lucide-react"

interface DocumentStatusBadgeProps {
  status: string
}

export function DocumentStatusBadge({ status }: DocumentStatusBadgeProps) {
  switch (status) {
    case 'COMPLETED':
      return null
    case 'PROCESSING':
    case 'PARTIAL':
      return (
        // 처리중/부분처리 상태 배지 스타일 변경: 배경색 #D8EFE9, 텍스트색 green-800
        <span className="status-badge inline-flex items-center px-1.5 py-0.5 text-xs font-medium text-green-800 bg-[#D8EFE9] rounded-full">
          <Clock className="w-3 h-3 mr-0.5" />
          처리중
        </span>
      )
    case 'ERROR':
    case 'FAILED':
      return (
        <span className="status-badge inline-flex items-center px-1.5 py-0.5 text-xs font-medium text-red-700 bg-red-100 rounded-full">
          <AlertCircle className="w-3 h-3 mr-0.5" />
          오류
        </span>
      )
    default:
      return (
        <span className="status-badge inline-flex items-center px-1.5 py-0.5 text-xs font-medium text-gray-700 bg-gray-100 rounded-full">
          <Clock className="w-3 h-3 mr-0.5" />
          대기중
        </span>
      )
  }
} 