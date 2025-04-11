/**
 * 컴포넌트 테스트 인덱스 페이지
 */
'use client';

import React from 'react';
import Link from 'next/link';

export default function TestIndexPage() {
  return (
    <div style={{ 
      padding: '40px', 
      maxWidth: '800px', 
      margin: '0 auto',
      fontFamily: 'Arial, sans-serif'
    }}>
      <h1 style={{ marginBottom: '30px', color: '#333' }}>AIChatArea 컴포넌트 테스트</h1>
      
      <p style={{ marginBottom: '20px', color: '#555', fontSize: '16px', lineHeight: '1.5' }}>
        이 페이지는 AIChatArea 컴포넌트 리팩토링 과정에서 개별 컴포넌트들을 테스트하기 위한 페이지입니다.
        각 컴포넌트에 대한 테스트 페이지로 이동할 수 있습니다.
      </p>
      
      <div style={{ 
        display: 'grid', 
        gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))', 
        gap: '20px',
        marginTop: '30px'
      }}>
        <TestCard 
          title="MessageBubble 테스트" 
          description="메시지 버블 컴포넌트의 렌더링 및 기능 테스트" 
          href="/components/chat/AIChatArea/test/message-bubble"
        />
        
        <TestCard 
          title="MessageList 테스트" 
          description="메시지 목록 컴포넌트의 렌더링 및 기능 테스트" 
          href="/components/chat/AIChatArea/test/message-list"
        />
        
        <TestCard 
          title="InputArea 테스트" 
          description="입력 영역 컴포넌트의 렌더링 및 기능 테스트" 
          href="/components/chat/AIChatArea/test/input-area"
        />
        
        <TestCard 
          title="추천질문 & 최신 업데이트" 
          description="추천질문과 최신 업데이트 종목 컴포넌트 테스트" 
          href="/components/chat/AIChatArea/test/recommended-questions-latest-updates"
        />
        
        <TestCard 
          title="전체 컴포넌트 테스트" 
          description="모든 컴포넌트를 통합한 종합 테스트" 
          href="/components/chat/AIChatArea/test/integration"
          isPrimary
        />
      </div>
    </div>
  );
}

// 테스트 카드 컴포넌트
function TestCard({
  title,
  description,
  href,
  isPrimary = false
}: {
  title: string;
  description: string;
  href: string;
  isPrimary?: boolean;
}) {
  return (
    <Link href={href} style={{ textDecoration: 'none' }}>
      <div style={{ 
        backgroundColor: isPrimary ? '#e7f5ff' : 'white',
        border: `1px solid ${isPrimary ? '#4dabf7' : '#ddd'}`,
        borderRadius: '8px',
        padding: '20px',
        transition: 'transform 0.2s, box-shadow 0.2s',
        height: '100%',
        boxShadow: isPrimary ? '0 4px 6px rgba(0, 0, 0, 0.1)' : '0 2px 4px rgba(0, 0, 0, 0.05)'
      }}
      onMouseEnter={(e) => {
        const target = e.currentTarget as HTMLDivElement;
        target.style.transform = 'translateY(-5px)';
        target.style.boxShadow = isPrimary 
          ? '0 10px 15px rgba(0, 0, 0, 0.1)' 
          : '0 8px 12px rgba(0, 0, 0, 0.05)';
      }}
      onMouseLeave={(e) => {
        const target = e.currentTarget as HTMLDivElement;
        target.style.transform = 'translateY(0)';
        target.style.boxShadow = isPrimary 
          ? '0 4px 6px rgba(0, 0, 0, 0.1)' 
          : '0 2px 4px rgba(0, 0, 0, 0.05)';
      }}
      >
        <h2 style={{ 
          marginTop: 0, 
          marginBottom: '10px', 
          color: isPrimary ? '#1971c2' : '#333',
          fontSize: '18px'
        }}>{title}</h2>
        
        <p style={{ 
          margin: 0, 
          color: '#666', 
          fontSize: '14px', 
          lineHeight: '1.4'
        }}>{description}</p>
      </div>
    </Link>
  );
} 