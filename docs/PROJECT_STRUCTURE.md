# 프로젝트 구조

이 문서는 Intellio 프로젝트의 전체 구조를 설명합니다.

## 프로젝트 개요

Intellio는 백엔드(FastAPI)와 프론트엔드(Next.js)로 구성된 풀스택 애플리케이션입니다.

## 디렉토리 구조

```
intellio/
├── backend/              # 백엔드 (FastAPI) 
│   ├── common/           # 공통 모듈(회원관리, text 처리, 임베딩 등)
│   │   ├── api/          # API 엔드포인트
│   │   ├── core/         
│   │   ├── models/       
│   │   ├── schemas/      
│   │   ├── services/     
│   │   └── utils/        
│   │
│   ├── doceasy/          # 닥이지 관련 모듈 ( Chat, Table mode 처리, 문서 프로젝트 관리 등 )
│   │   ├── api/          # API 엔드포인트
│   │   ├── core/         
│   │   ├── models/       
│   │   ├── schemas/      
│   │   ├── services/     
│   │   ├── tests/        
│   │   └── workers/      # 백그라운드 작업
│   ├── stockeasy/          # 스탁이지 관련 모듈 ( 작업 예정 )
│   │   ├── api/          # API 엔드포인트
│   │   ├── core/         
│   │
│   ├── migrations/       # 데이터베이스 마이그레이션
│   ├── credentials/      # api key 등
│
├── frontend/            ### 프론트엔드 (Next.js)
│   ├── common/          ## 공통 컴포넌트
│   │   ├── components/   # 재사용 가능한 컴포넌트
│   │   └── lib/          # 유틸리티 함수
│   │
│   ├── doceasy/         # 문서 처리 관련 프론트엔드
│   │   ├── app/         # Next.js 앱 라우터
│   │   └── types/       # TypeScript 타입 정의
│   │
│   ├── main/            ## 인텔리오 홈페이지
│   │   ├── app/         # Next.js 앱 라우터
│   │   ├── error/       # 에러 처리
│   │   └── styles/      # 스타일 파일
│   │
│   └── stockeasy/       # 주식 관련 모듈
│       ├── app/         
│       ├── components/  # 컴포넌트
│       └── lib/         # 유틸리티 함수
│
└── docs/                # 프로젝트 문서
```

## 주요 디렉토리 설명

### Backend

- **common**: 여러 모듈에서 공통으로 사용되는 코드를 포함
- **doceasy**: 문서 처리와 관련된 핵심 비즈니스 로직
- **migrations**: 데이터베이스 스키마 변경 관리
- **tests**: 단위 테스트 및 통합 테스트

### Frontend

- **common**: 재사용 가능한 UI 컴포넌트 및 유틸리티
- **doceasy**: 문서 처리 관련 프론트엔드 애플리케이션
- **main**: 메인 애플리케이션 진입점
- **stockeasy**: 주식 관련 기능 모듈

## 기술 스택

### Backend
- FastAPI (Python)
- SQLAlchemy (ORM)
- Pydantic
- Alembic (마이그레이션)

### Frontend
- Next.js (React)
- TypeScript
- Tailwind CSS
- Shadcn UI
- Radix UI
