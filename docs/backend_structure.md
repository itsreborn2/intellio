# 백엔드 폴더 구조

## 1. 루트 디렉토리 구조

```
backend_new/ 
├── alembic/              # 데이터베이스 마이그레이션 관련
├── app/                  # 메인 애플리케이션 코드
├── logs/                 # 로그 파일 저장
├── migrations/           # 데이터베이스 마이그레이션 스크립트
├── scripts/              # 유틸리티 스크립트
├── tests/                # 테스트 코드
├── venv/                 # 가상 환경
├── .env                  # 환경 변수 파일
├── .env.example          # 환경 변수 예시 파일
├── alembic.ini           # Alembic 설정 파일
├── pytest.ini           # PyTest 설정 파일
└── requirements.txt      # 의존성 패키지 목록
```

## 2. app 디렉토리 구조

```
app/
├── api/                  # API 엔드포인트 정의
│   └── v1/              # API 버전 1
│       ├── auth.py      # 인증 관련 엔드포인트
│       ├── project.py   # 프로젝트 관련 엔드포인트
│       ├── session.py   # 세션 관련 엔드포인트
│       └── ...
│
├── core/                 # 핵심 설정 및 유틸리티
│   ├── config.py        # 애플리케이션 설정
│   ├── security.py      # 보안 관련 유틸리티
│   ├── deps.py          # 의존성 주입
│   └── ...
│
├── models/              # 데이터베이스 모델
│   ├── base.py         # 기본 모델 클래스
│   ├── user.py         # 사용자 모델
│   ├── project.py      # 프로젝트 모델
│   └── ...
│
├── schemas/            # Pydantic 스키마
│   ├── user.py        # 사용자 관련 스키마
│   ├── project.py     # 프로젝트 관련 스키마
│   └── ...
│
├── services/          # 비즈니스 로직
│   ├── user.py       # 사용자 관련 서비스
│   ├── project.py    # 프로젝트 관련 서비스
│   ├── oauth.py      # OAuth 인증 서비스
│   └── ...
│
├── workers/          # 백그라운드 작업 처리
│   ├── celery.py    # Celery 설정
│   └── tasks.py     # Celery 태스크
│
└── main.py          # FastAPI 애플리케이션 진입점
```

## 3. 주요 컴포넌트 설명

### 3.1 API (app/api)
- RESTful API 엔드포인트 정의
- 버전별로 구분된 라우터
- 요청/응답 처리 및 라우팅

### 3.2 Core (app/core)
- 애플리케이션 설정 및 환경 변수
- 보안 관련 유틸리티 (인증, 암호화 등)
- 의존성 주입 및 미들웨어

### 3.3 Models (app/models)
- SQLAlchemy ORM 모델
- 데이터베이스 테이블 구조 정의
- 관계 및 제약 조건 정의

### 3.4 Schemas (app/schemas)
- Pydantic 모델
- 요청/응답 데이터 검증
- API 문서화를 위한 스키마

### 3.5 Services (app/services)
- 비즈니스 로직 구현
- 데이터베이스 작업 처리
- 외부 서비스 통합 (OAuth 등)

### 3.6 Workers (app/workers)
- 비동기 작업 처리
- 백그라운드 태스크 관리
- Celery 워커 설정

## 4. 설정 파일

### 4.1 환경 변수 (.env)
```env
# 데이터베이스 설정
DB_HOST=localhost
DB_PORT=5432
DB_USER=user
DB_PASS=password
DB_NAME=dbname

# OAuth 설정
GOOGLE_CLIENT_ID=your_client_id
GOOGLE_CLIENT_SECRET=your_client_secret
NAVER_CLIENT_ID=your_client_id
NAVER_CLIENT_SECRET=your_client_secret
KAKAO_CLIENT_ID=your_client_id
KAKAO_CLIENT_SECRET=your_client_secret

# 보안 설정
SECRET_KEY=your_secret_key
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

### 4.2 의존성 (requirements.txt)
- FastAPI
- SQLAlchemy
- Alembic
- Pydantic
- Python-Jose
- Passlib
- Celery
- 기타 필요한 패키지

## 5. 개발 가이드라인

1. **API 버전 관리**
   - 새로운 API 버전은 `app/api/` 하위에 새 버전 디렉토리 생성
   - 기존 API 변경 시 하위 호환성 유지

2. **코드 구조**
   - 비즈니스 로직은 services/에 구현
   - API 엔드포인트는 단순 라우팅만 담당
   - 복잡한 로직은 적절한 서비스로 분리

3. **데이터베이스**
   - 모델 변경 시 Alembic 마이그레이션 생성
   - 관계 설정 시 cascade 옵션 주의
   - 인덱스 적절히 사용
