# 프로젝트 구조

### 백엔드 구조 (backend_new/)
```
backend_new/
├── alembic/                # 데이터베이스 마이그레이션
│   ├── versions/          # 마이그레이션 버전 파일들
│   └── env.py            # 마이그레이션 환경 설정
├── app/                    # 메인 애플리케이션
│   ├── api/              # API 엔드포인트
│   │   ├── v1/          # API 버전 1
│   │   │   ├── auth.py      # 인증 관련 API
│   │   │   ├── projects.py  # 프로젝트 관련 API
│   │   │   └── documents.py # 문서 관련 API
│   │   └── deps.py      # API 의존성
│   ├── core/            # 핵심 설정 및 유틸리티
│   │   ├── config.py    # 환경 설정
│   │   ├── security.py  # 보안 관련
│   │   └── celery_app.py # Celery 설정
│   ├── credentials/     # 인증 관련
│   │   └── auth.py      # 인증 로직
│   ├── crud/           # 데이터베이스 CRUD 작업
│   │   ├── base.py     # 기본 CRUD 작업
│   │   ├── project.py  # 프로젝트 CRUD
│   │   └── document.py # 문서 CRUD
│   ├── models/         # 데이터베이스 모델
│   │   ├── project.py  # 프로젝트 모델
│   │   ├── document.py # 문서 모델
│   │   └── user.py     # 사용자 모델
│   ├── schemas/        # Pydantic 모델
│   │   ├── project.py  # 프로젝트 스키마
│   │   └── document.py # 문서 스키마
│   ├── services/       # 비즈니스 로직
│   │   ├── project.py  # 프로젝트 서비스
│   │   └── document.py # 문서 서비스
│   ├── websockets/     # 웹소켓 처리
│   │   └── connection.py # 웹소켓 연결 관리
│   ├── workers/        # Celery 워커
│   │   ├── tasks.py    # Celery 태스크
│   │   └── utils.py    # 워커 유틸리티
│   └── main.py         # 애플리케이션 진입점
├── migrations/          # 데이터베이스 마이그레이션 스크립트
├── scripts/            # 유틸리티 스크립트
├── tests/              # 테스트 코드
│   ├── api/           # API 테스트
│   ├── crud/          # CRUD 테스트
│   └── services/      # 서비스 테스트
├── .env               # 환경 변수
└── requirements.txt    # Python 의존성
```

### 프론트엔드 구조 (frontend/)
```
frontend/
├── app/                # Next.js 13+ 앱 디렉토리
│   ├── auth/          # 인증 관련 페이지
│   ├── projects/      # 프로젝트 관련 페이지
│   └── documents/     # 문서 관련 페이지
├── components/         # 재사용 가능한 컴포넌트
│   ├── common/        # 공통 컴포넌트
│   │   ├── Header.tsx        # 헤더 컴포넌트
│   │   ├── Sidebar.tsx       # 사이드바 메인 컴포넌트
│   │   ├── sidebar/         # 사이드바 관련 컴포넌트
│   │   │   └── ProjectCategorySection.tsx  # 프로젝트 카테고리 섹션
│   │   ├── Button/          # 버튼 컴포넌트
│   │   ├── Input/           # 입력 컴포넌트
│   │   └── Modal/           # 모달 컴포넌트
│   ├── layout/        # 레이아웃 컴포넌트
│   └── project/       # 프로젝트 관련 컴포넌트
├── contexts/          # React Context
│   ├── AuthContext.ts # 인증 컨텍스트
│   └── ProjectContext.ts # 프로젝트 컨텍스트
├── hooks/             # 커스텀 React Hooks
│   ├── useAuth.ts     # 인증 훅
│   └── useProject.ts  # 프로젝트 훅
├── lib/               # 유틸리티 함수
│   ├── api.ts        # API 클라이언트
│   └── utils.ts      # 유틸리티 함수
├── services/          # API 통신 서비스
│   ├── auth.ts       # 인증 서비스
│   └── project.ts    # 프로젝트 서비스
├── styles/            # CSS 스타일
│   ├── globals.css   # 전역 스타일
│   └── components/   # 컴포넌트별 스타일
├── templates/         # 페이지 템플릿
├── types/            # TypeScript 타입 정의
│   ├── project.ts    # 프로젝트 타입
│   └── document.ts   # 문서 타입
├── .env              # 환경 변수
├── next.config.mjs   # Next.js 설정
├── package.json      # 의존성 관리
├── tailwind.config.js # Tailwind CSS 설정
└── tsconfig.json     # TypeScript 설정

# 프로젝트 설정 가이드라인

1. 파일 인코딩
   - 모든 파일은 UTF-8 인코딩 사용
   - BOM(Byte Order Mark) 사용하지 않음
   - 줄바꿈은 LF(Line Feed) 사용

2. 개발 환경
   - OS: Windows
   - 터미널: PowerShell
   - 프론트엔드: Next.js 13+
   - 백엔드: FastAPI (Python)

3. 프로젝트 우선순위
   1. 안정성
   2. 속도
   3. 유지보수
   4. 보안

4. 개발 프로세스
   - 작은 단위부터 테스트 진행
   - 모든 명령어는 PowerShell 문법 기준
   - 모든 명령어는 'insert to terminal' 버튼으로 제공

5. Git 관리
   - 모든 커밋 메시지는 큰따옴표("") 사용
   - 브랜치명도 큰따옴표("") 사용