'use client'

import { Toaster } from 'sonner'

export function ToastProvider() {
  return (
    <Toaster 
      position="top-center"
      expand={false}
      richColors
      closeButton
    />
  )
} 