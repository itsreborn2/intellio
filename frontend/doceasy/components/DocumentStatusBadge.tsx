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
        <span className="inline-flex items-center px-2 py-1 text-xs font-medium text-blue-700 bg-blue-100 rounded-full">
          <Clock className="w-3 h-3 mr-1" />
          처리중
        </span>
      )
    case 'ERROR':
    case 'FAILED':
      return (
        <span className="inline-flex items-center px-2 py-1 text-xs font-medium text-red-700 bg-red-100 rounded-full">
          <AlertCircle className="w-3 h-3 mr-1" />
          오류
        </span>
      )
    default:
      return (
        <span className="inline-flex items-center px-2 py-1 text-xs font-medium text-gray-700 bg-gray-100 rounded-full">
          <Clock className="w-3 h-3 mr-1" />
          대기중
        </span>
      )
  }
} 