'use client'

import { CSSProperties } from 'react'

interface LoadingProps {
  isMobile: boolean
  windowWidth: number
  elapsedTime: number
}

// 기본 로딩 스피너
export function LoadingSpinner() {
  return (
    <div className="loading-spinner" style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      margin: '12px 0'
    }}>
      <div style={{
        width: '36px',
        height: '36px',
        borderRadius: '50%',
        border: '3px solid #f3f3f3',
        borderTop: '3px solid #10A37F',
        animation: 'spin 1s linear infinite',
      }}></div>
      <style jsx>{`
        @keyframes spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  )
}

// 검색 중 타이머
export function SearchTimer({ isMobile, windowWidth, elapsedTime }: LoadingProps) {
  return (
    <div className="search-timer" style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      gap: isMobile ? '6px' : '8px',
      backgroundColor: '#D8EFE9',
      padding: isMobile ? '6px 10px' : (windowWidth < 768 ? '7px 11px' : '8px 12px'),
      borderRadius: isMobile ? '6px' : '8px',
      boxShadow: '0 2px 5px rgba(0, 0, 0, 0.05)',
      marginBottom: isMobile ? '10px' : '12px',
      maxWidth: '100%',
      wordBreak: 'break-word'
    }}>
      <div style={{
        position: 'relative',
        width: isMobile ? '24px' : '28px',
        height: isMobile ? '24px' : '28px',
        borderRadius: '50%',
        border: isMobile ? '1.5px solid #e1e1e1' : '2px solid #e1e1e1',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexShrink: 0
      }}>
        <div style={{
          position: 'absolute',
          top: '50%',
          left: '50%',
          width: isMobile ? '12px' : '14px',
          height: isMobile ? '1.5px' : '2px',
          background: 'transparent',
          transform: 'rotate(0deg) translateX(0)',
          transformOrigin: '0 0',
          zIndex: 2
        }}>
          <div style={{
            position: 'absolute',
            width: isMobile ? '6px' : '8px',
            height: isMobile ? '1.5px' : '2px',
            backgroundColor: '#10A37F',
            animation: 'stopwatch-sec 60s steps(60, end) infinite',
            transformOrigin: 'left center'
          }}></div>
        </div>
        <div style={{
          width: isMobile ? '5px' : '6px',
          height: isMobile ? '5px' : '6px',
          backgroundColor: '#10A37F',
          borderRadius: '50%',
          zIndex: 3
        }}></div>
      </div>
      <div style={{
        fontFamily: 'monospace',
        fontSize: isMobile ? '14px' : (windowWidth < 768 ? '15px' : '16px'),
        fontWeight: 'bold',
        color: '#555',
        flexShrink: 0
      }}>
        {Math.floor(elapsedTime / 60).toString().padStart(2, '0')}:{(elapsedTime % 60).toString().padStart(2, '0')}
      </div>
      <style jsx>{`
        @keyframes stopwatch-sec {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  )
}

// 검색 애니메이션
export function SearchingAnimation({ isMobile, windowWidth }: Omit<LoadingProps, 'elapsedTime'>) {
  return (
    <div className="searching-animation" style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'flex-start',
      padding: isMobile ? '8px 12px' : (windowWidth < 768 ? '9px 13px' : '10px 14px'),
      backgroundColor: '#D8EFE9',
      borderRadius: isMobile ? '10px' : '12px',
      boxShadow: '0 1px 2px rgba(0, 0, 0, 0.1)',
      maxWidth: isMobile ? '95%' : (windowWidth < 768 ? '90%' : '85%'),
      marginBottom: isMobile ? '12px' : '16px',
      width: 'auto',
      wordBreak: 'break-word'
    }}>
      <div style={{
        fontSize: isMobile ? '14px' : (windowWidth < 768 ? '15px' : '16px'),
        marginBottom: isMobile ? '6px' : '8px',
        color: '#555',
        display: 'flex',
        alignItems: 'center',
        gap: isMobile ? '6px' : '8px',
        maxWidth: '100%',
        flexWrap: 'wrap'
      }}>
        <div className="loading-icon" style={{
          width: isMobile ? '14px' : '16px',
          height: isMobile ? '14px' : '16px',
          borderRadius: '50%',
          border: isMobile ? '1.5px solid #f3f3f3' : '2px solid #f3f3f3',
          borderTop: isMobile ? '1.5px solid #10A37F' : '2px solid #10A37F',
          animation: 'spin 1s linear infinite',
          flexShrink: 0
        }}></div>
        <span>정보를 검색 중입니다...</span>
      </div>
      <SearchStep text="종목 정보 확인 중" delay={0} isMobile={isMobile} windowWidth={windowWidth} />
      <SearchStep text="투자 분석 보고서 조회 중" delay={0.5} isMobile={isMobile} windowWidth={windowWidth} />
      <SearchStep text="최신 종목 뉴스 분석 중" delay={1} isMobile={isMobile} windowWidth={windowWidth} />
      <style jsx>{`
        @keyframes spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
        @keyframes pulse {
          0%, 100% { opacity: 0.3; }
          50% { opacity: 1; }
        }
      `}</style>
    </div>
  )
}

// 검색 단계 컴포넌트
function SearchStep({ text, delay, isMobile, windowWidth }: { 
  text: string, 
  delay: number, 
  isMobile: boolean, 
  windowWidth: number 
}) {
  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: isMobile ? '5px' : '6px',
      margin: isMobile ? '3px 0' : '4px 0',
      fontSize: isMobile ? '13px' : (windowWidth < 768 ? '14px' : '16px'),
      color: '#888',
      maxWidth: '100%',
      flexWrap: 'wrap'
    }}>
      <div className="dot" style={{
        width: isMobile ? '5px' : '6px',
        height: isMobile ? '5px' : '6px',
        borderRadius: '50%',
        backgroundColor: '#3498db',
        flexShrink: 0,
        opacity: 0.5,
        animation: 'pulse 1.5s infinite',
        animationDelay: `${delay}s`
      }}></div>
      <span>{text}</span>
    </div>
  )
} 