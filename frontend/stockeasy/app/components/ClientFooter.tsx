'use client'

import { useEffect, useState } from 'react'

// 클라이언트 사이드에서 모바일 환경 체크 및 저작권 정보 표시
export default function ClientFooter() {
  const [isMobile, setIsMobile] = useState(false)

  useEffect(() => {
    // 화면 크기에 따라 모바일 여부 판단
    const checkMobile = () => {
      setIsMobile(window.innerWidth < 768)
    }

    // 초기 체크
    checkMobile()

    // 화면 크기 변경 시 체크
    window.addEventListener('resize', checkMobile)
    
    // 컴포넌트 언마운트 시 이벤트 리스너 제거
    return () => {
      window.removeEventListener('resize', checkMobile)
    }
  }, [])

  if (isMobile) {
    return null
  }

  return (
    <div style={{
      width: '65%', 
      textAlign: 'center',
      paddingTop: '10px',
      paddingBottom: '10px',
      margin: '0 auto',
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'center', 
      height: '20px',
      position: 'relative',
      marginTop: '5px',
      marginBottom: '5px',
      zIndex: 5, 
      backgroundColor: 'rgba(244, 244, 244, 0.8)'
    }}>
      <div style={{
        fontSize: '13px',
        color: '#888',
        fontWeight: '300'
      }}>
        2025 Intellio Corporation All Rights Reserved.
      </div>
    </div>
  )
}
