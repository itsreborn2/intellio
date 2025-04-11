# AIChatArea 컴포넌트 리팩토링 계획

## 문제 분석

현재 `AIChatArea.tsx` 파일은 다음과 같은 문제점을 가지고 있습니다:

1. **코드 크기**: 2656줄에 달하는 매우 큰 단일 컴포넌트
2. **책임 과부하**: 입력 처리, 메시지 표시, UI 렌더링, 데이터 처리 등 다양한 책임을 한 컴포넌트가 모두 담당
3. **상태 관리 복잡성**: 다수의 상태(useState)가 하나의 컴포넌트에 집중
4. **유지보수 어려움**: 새로운 기능 추가 시 파일이 계속 커질 위험
5. **반응형 처리 중복**: 모바일/PC 대응 로직이 여러 곳에 분산

## 리팩토링 목표

1. **컴포넌트 모듈화**: 단일 책임 원칙에 따라 컴포넌트 분리
2. **상태 관리 최적화**: Zustand 스토어 활용 강화 및 컨텍스트 API 도입
3. **반응형 처리 개선**: 반응형 로직을 커스텀 훅으로 분리
4. **성능 최적화**: 메모이제이션 및 가상화 기법 적용
5. **확장성 개선**: 새로운 기능을 쉽게 추가할 수 있는 구조 설계

## 새로운 폴더 구조

```
frontend/stockeasy/app/components/chat/
├── AIChatArea/ (메인 컴포넌트 디렉토리)
│   ├── index.tsx (최상위 컴포넌트)
│   ├── context/ (컨텍스트)
│   │   ├── ChatContext.tsx
│   │   └── StockSelectorContext.tsx
│   ├── hooks/ (커스텀 훅)
│   │   ├── useIsMobile.ts
│   │   ├── useStockSearch.ts
│   │   ├── useMessageProcessing.ts
│   │   ├── useTimers.ts
│   │   └── useMediaQuery.ts
│   ├── layouts/ (레이아웃 컴포넌트)
│   │   ├── ChatLayout.tsx
│   │   └── InputCenteredLayout.tsx
│   ├── components/ (하위 컴포넌트)
│   │   ├── MessageList.tsx
│   │   ├── MessageBubble.tsx
│   │   ├── StatusMessage.tsx
│   │   ├── InputArea.tsx
│   │   ├── StockSuggestions.tsx
│   │   ├── RecommendedQuestions.tsx
│   │   ├── LatestUpdates.tsx
│   │   └── CopyButton.tsx
│   └── utils/ (유틸리티 함수)
│       ├── messageFormatters.ts
│       ├── stockDataUtils.ts
│       └── styleUtils.ts
└── types/ (타입 정의)
    ├── chat.ts
    └── stock.ts
```

## 주요 구현 내용

### 1. 컨텍스트 API를 통한 상태 관리

```typescript
// context/ChatContext.tsx
import React, { createContext, useContext, useReducer, ReactNode } from 'react'
import { ChatMessage, StockOption } from '../types'

interface ChatState {
  messages: ChatMessage[]
  isProcessing: boolean
  selectedStock: StockOption | null
  isInputCentered: boolean
  // 기타 상태들...
}

// 컨텍스트 생성 및 구현...
```

### 2. 공통 커스텀 훅 분리

```typescript
// hooks/useIsMobile.ts
import { useState, useEffect } from 'react'

export function useIsMobile() {
  const [isMobile, setIsMobile] = useState(false)

  useEffect(() => {
    const checkIsMobile = () => {
      setIsMobile(window.innerWidth < 768)
    }

    checkIsMobile()
    window.addEventListener('resize', checkIsMobile)
    return () => window.removeEventListener('resize', checkIsMobile)
  }, [])

  return isMobile
}
```

### 3. 메시지 처리 로직 분리

```typescript
// hooks/useMessageProcessing.ts
import { useState, useRef } from 'react'
import { useChatStore } from '@/stores/chatStore'
import { useTokenUsageStore } from '@/stores/tokenUsageStore'
import { useQuestionCountStore } from '@/stores/questionCountStore'

export function useMessageProcessing() {
  // 메시지 전송 및 처리 로직 구현...
}
```

### 4. 핵심 컴포넌트 분리

```typescript
// components/MessageList.tsx
import React, { useRef, useEffect } from 'react'
import { useChatContext } from '../context/ChatContext'
import MessageBubble from './MessageBubble'
import StatusMessage from './StatusMessage'

export default function MessageList() {
  // 메시지 목록 표시 로직 구현...
}

// components/InputArea.tsx
import React, { useRef } from 'react'
import { useChatContext } from '../context/ChatContext'
import StockSuggestions from './StockSuggestions'

export default function InputArea() {
  // 입력 영역 로직 구현...
}
```

## 구현 전략 및 순서

### 1단계: 타입 정의 및 기본 구조 설정
- 타입 파일 분리 (stock.ts, chat.ts)
- 폴더 구조 설정

### 2단계: 커스텀 훅 분리
- 반응형 UI 관련 훅(useIsMobile, useMediaQuery)
- 종목 검색 관련 훅(useStockSearch)
- 타이머 관련 훅(useTimers)

### 3단계: 컨텍스트 구현
- ChatContext.tsx 구현
- StockSelectorContext.tsx 구현

### 4단계: 핵심 컴포넌트 분리
- MessageBubble, StatusMessage 분리
- InputArea, StockSuggestions 분리
- RecommendedQuestions, LatestUpdates 분리

### 5단계: 레이아웃 컴포넌트 구현
- ChatLayout.tsx
- InputCenteredLayout.tsx

### 6단계: 메인 컴포넌트 재구성
- index.tsx 파일 작성
- 기존 AIChatArea.tsx 파일의 로직을 분산 배치

### 7단계: 유틸리티 함수 분리 및 최적화
- messageFormatters.ts
- stockDataUtils.ts
- styleUtils.ts

### 8단계: 테스트 및 최적화
- 각 컴포넌트 테스트
- 성능 최적화
- 메모이제이션 적용

## 예상 효과

1. **유지보수성 향상**: 개별 컴포넌트가 단일 책임을 가지므로 버그 수정과 기능 추가가 용이
2. **코드 재사용**: 분리된 컴포넌트는 다른 부분에서도 재사용 가능
3. **성능 최적화**: 컴포넌트별 렌더링 최적화 가능
4. **협업 효율성**: 여러 개발자가 각자 다른 컴포넌트를 동시에 작업 가능
5. **확장성**: 새로운 기능 추가 시 기존 코드 수정 없이 새 컴포넌트 추가 가능

## 향후 확장 고려사항

1. 가상화 기법을 적용한 대량 메시지 처리
2. 테마 관리 시스템 도입
3. 애니메이션 최적화
4. 접근성 개선
5. 국제화(i18n) 지원 