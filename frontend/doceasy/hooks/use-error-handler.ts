'use client'

import { toast } from 'sonner'
import { useRouter } from 'next/navigation'

interface ErrorResponse {
  detail: string
  status: number
}

export function useErrorHandler() {
  const router = useRouter()

  const handleError = (error: any) => {
    const status = error?.response?.status
    const detail = error?.response?.data?.detail || '알 수 없는 오류가 발생했습니다.'

    switch (status) {
      case 401:
        toast.error(detail)
        router.push('/auth/login')
        break
      case 403:
        toast.error('접근 권한이 없습니다.')
        break
      case 404:
        toast.error('요청하신 리소스를 찾을 수 없습니다.')
        break
      case 500:
        toast.error('서버 오류가 발생했습니다. 잠시 후 다시 시도해주세요.')
        break
      default:
        toast.error(detail)
    }
  }

  return { handleError }
} 