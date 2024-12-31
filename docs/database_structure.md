# Intellio 데이터베이스 구조 문서

## 1. 데이터베이스 시스템 구성

### 1.1 PostgreSQL (주 데이터베이스)
- 모든 메타데이터와 관계형 데이터 저장
- ACID 특성을 활용한 안정적인 데이터 관리
- 사용자, 프로젝트, 문서 메타데이터 관리

### 1.2 Pinecone (벡터 데이터베이스)
- 문서 청크의 벡터 임베딩 저장
- 고성능 벡터 유사도 검색 지원
- PostgreSQL과의 연동을 통한 통합 검색 지원

## 2. 테이블 구조

### 2.1 Document (documents)
문서의 기본 정보를 저장하는 테이블

#### 필드 구조
| 필드명 | 타입 | 설명 |
|--------|------|------|
| id | UUID | 고유 식별자 |
| project_id | UUID | 프로젝트 연결 (FK) |
| filename | String(255) | 원본 파일명 |
| file_path | String(1000) | 저장 경로 |
| file_type | String(100) | 파일 형식 (txt, pdf, docx 등) |
| mime_type | String(100) | MIME 타입 |
| file_size | Integer | 파일 크기 |
| status | String(20) | 문서 처리 상태 |
| error_message | String(1000) | 오류 메시지 |
| extracted_text | Text | 추출된 텍스트 |
| embedding_ids | String | Pinecone 임베딩 ID (JSON) |
| created_at | DateTime | 생성 시간 |
| updated_at | DateTime | 수정 시간 |

### 2.2 DocumentChunk (document_chunks)
대용량 문서의 분할된 청크를 저장하는 테이블

#### 필드 구조
| 필드명 | 타입 | 설명 |
|--------|------|------|
| id | UUID | 고유 식별자 |
| document_id | UUID | 원본 문서 연결 (FK) |
| content | Text | 청크 내용 |
| embedding | String | 벡터 임베딩 데이터 |
| chunk_metadata | String | 청크 관련 메타데이터 |
| created_at | DateTime | 생성 시간 |
| updated_at | DateTime | 수정 시간 |

### 2.3 Project (projects)
문서 분석 프로젝트 정보를 저장하는 테이블

#### 필드 구조
| 필드명 | 타입 | 설명 |
|--------|------|------|
| id | UUID | 고유 식별자 |
| name | String(255) | 프로젝트명 |
| description | Text | 프로젝트 설명 |
| is_temporary | Boolean | 임시/영구 여부 |
| user_category | String(255) | 사용자 정의 카테고리 |
| session_id | String(255) | 세션 연결 (FK) |
| user_id | UUID | 사용자 연결 (FK) |
| project_metadata | Text | 프로젝트 메타데이터 |
| content_data | Text | 컨텐츠 데이터 |
| embedding_refs | Text | 임베딩 참조 정보 |
| created_at | DateTime | 생성 시간 |
| updated_at | DateTime | 수정 시간 |

### 2.4 User (users)
사용자 정보를 관리하는 테이블

#### 필드 구조
| 필드명 | 타입 | 설명 |
|--------|------|------|
| id | UUID | 고유 식별자 |
| email | String(255) | 이메일 (unique) |
| name | String(100) | 사용자명 |
| hashed_password | String(255) | 암호화된 비밀번호 |
| is_active | Boolean | 활성화 상태 |
| is_superuser | Boolean | 관리자 여부 |
| created_at | DateTime | 생성 시간 |
| updated_at | DateTime | 수정 시간 |

### 2.5 Session (sessions)
사용자 세션을 관리하는 테이블

#### 필드 구조
| 필드명 | 타입 | 설명 |
|--------|------|------|
| id | UUID | 고유 식별자 |
| session_id | String(100) | 세션 식별자 |
| user_id | UUID | 사용자 연결 (FK) |
| is_anonymous | Boolean | 익명 세션 여부 |
| created_at | DateTime | 생성 시간 |
| last_accessed_at | DateTime | 마지막 접근 시간 |
| updated_at | DateTime | 수정 시간 |

## 3. 테이블 관계도
```
User (1) ----< Session (1) ----< Project (1) ----< Document (1) ----< DocumentChunk (N)
```

## 4. 참고 사항
- 모든 테이블은 created_at, updated_at 필드를 포함
- UUID를 기본 식별자로 사용
- Soft Delete 패턴 적용 검토 필요

## 5. 상세 구현 명세

### 5.1 문서 상태 관리 (Document Status)

#### 5.1.1 상태 정의
| 상태 | 설명 | 다음 상태 |
|------|------|-----------|
| REGISTERED | 문서 등록 완료 | PROCESSING, ERROR |
| PROCESSING | 문서 처리 중 | EXTRACTED, ERROR |
| EXTRACTED | 텍스트 추출 완료 | EMBEDDING, ERROR |
| EMBEDDING | 임베딩 생성 중 | COMPLETED, ERROR |
| COMPLETED | 모든 처리 완료 | - |
| ERROR | 처리 중 오류 발생 | REGISTERED (재시도) |

#### 5.1.2 상태별 처리 로직
1. **REGISTERED**
   - 문서 기본 정보 검증
   - 파일 형식 확인
   - 처리 우선순위 할당

2. **PROCESSING**
   - OCR 처리 (필요시)
   - 텍스트 추출
   - 메타데이터 추출

3. **EXTRACTED**
   - 텍스트 정규화
   - 청크 분할
   - 임시 저장

4. **EMBEDDING**
   - 청크별 임베딩 생성
   - Pinecone 저장
   - 참조 정보 갱신

5. **COMPLETED**
   - 최종 검증
   - 인덱싱
   - 검색 가능 상태 설정

### 5.2 청크 관리 전략

#### 5.2.1 청크 크기 최적화
- 텍스트: 512~1024 토큰
- 표/도표: 개별 단위로 분리
- 이미지: 문맥 단위로 분리

#### 5.2.2 청크 메타데이터 구조
```json
{
    "chunk_index": 1,
    "total_chunks": 10,
    "page_number": 1,
    "content_type": "text|table|image",
    "token_count": 512,
    "parent_context": "section_id",
    "processing_info": {
        "processor_version": "1.0",
        "processing_date": "2024-12-31",
        "confidence_score": 0.95
    }
}
```

#### 5.2.3 청크 재처리 전략
1. 임베딩 모델 업데이트 시
2. 청크 크기 정책 변경 시
3. 오류 복구 시

### 5.3 임베딩 관리

#### 5.3.1 Pinecone 연동 구조
```
PostgreSQL (Document/Chunk) <-> 중간 레이어 <-> Pinecone
```

#### 5.3.2 임베딩 동기화 전략
1. **저장 시점**
   - 청크 생성 직후
   - 배치 처리 (대량 문서)
   - 재처리 요청 시

2. **업데이트 정책**
   - 증분 업데이트
   - 전체 갱신 회피
   - 버전 관리 통한 이력 추적

#### 5.3.3 임베딩 참조 구조
```json
{
    "pinecone_ids": ["id1", "id2"],
    "namespace": "project_123",
    "model_version": "v1",
    "last_sync": "2024-12-31T00:00:00Z"
}
```

### 5.4 세션 관리

#### 5.4.1 세션 정책
- 기본 만료 시간: 30일 (마지막 접근 시간 기준)
- 자동 연장: 사용자 활동 시 마다 만료 시간 갱신
- 세션 저장소: PostgreSQL 데이터베이스
- 세션ID 관리: unique 인덱스로 중복 방지

#### 5.4.2 세션 상태
1. **인증 상태**
   - 로그인 사용자: user_id 연결, is_anonymous=false
   - 익명 사용자: user_id=null, is_anonymous=true

2. **만료 처리**
   - 자동 만료: 마지막 접근 후 30일
   - 수동 만료: 로그아웃 시 세션 삭제

3. **갱신 정책**
   - API 요청시 마다 last_accessed_at 갱신
   - 만료된 세션 재사용 불가

#### 5.4.3 쿠키 설정
1. **기본 설정**
   ```python
   response.set_cookie(
       key="session_id",
       value=session.session_id,
       max_age=30 * 24 * 60 * 60,  # 30일
       httponly=True,
       secure=True,     # HTTPS 전용
       samesite="strict"  # CSRF 방지
   )
   ```

2. **보안 기능**
   - `httponly`: JavaScript에서 쿠키 접근 방지
   - `secure`: HTTPS 연결에서만 쿠키 전송
   - `samesite`: CSRF 공격 방지
   - `max_age`: 30일 후 자동 만료

3. **쿠키 삭제**
   - 로그아웃 시 자동 삭제
   - 동일한 보안 설정 유지

#### 5.4.4 세션 관리 API
1. **세션 생성**
   - 회원가입: `/api/v1/auth/register`
   - 로그인: `/api/v1/auth/login`
   - 익명 세션: `/api/v1/session`

2. **세션 조회/삭제**
   - 현재 세션 조회: `/api/v1/session/current`
   - 세션 삭제: `/api/v1/session/current` (DELETE)
   - 만료 세션 정리: `/api/v1/session/cleanup`

#### 5.4.5 향후 개선 사항
1. **세션 관리 강화**
   - 동시 세션 제한
   - 세션 하이재킹 방지
   - 세션 ID 재생성 정책

2. **모니터링**
   - 세션 생성/만료 로깅
   - 비정상 접근 탐지
   - 성능 모니터링

### 5.5 프로젝트 메타데이터

#### 5.5.1 project_metadata 구조
```json
{
    "version": "1.0",
    "settings": {
        "chunk_size": 512,
        "embedding_model": "v1",
        "language": "ko"
    },
    "processing_rules": {
        "ocr_enabled": true,
        "table_extraction": true
    },
    "custom_config": {
        "user_defined_tags": [],
        "category_rules": {}
    }
}
```

#### 5.5.2 content_data 구조
```json
{
    "summary": "프로젝트 요약",
    "key_points": [],
    "document_count": 10,
    "total_chunks": 100,
    "last_analysis": "2024-12-31T00:00:00Z"
}
```

## 6. 개발 우선순위

### 6.1 즉시 개선 항목
1. 문서 상태 관리 시스템 구현
2. 청크 메타데이터 구조화
3. 세션 관리 정책 적용

### 6.2 단기 개선 항목
1. 임베딩 동기화 전략 구현
2. 모니터링 시스템 구축
3. 백업/복구 자동화

## 7. 추가 검토 사항

### 7.1 데이터 무결성 강화
1. **외래 키 제약 조건**
   - Document-Project 간 CASCADE 동작 검증
   - Session-User 간 제약 조건 최적화
   - 순환 참조 가능성 검토

2. **인덱스 최적화**
   - 검색 패턴 분석 기반 인덱스 설계
   - 복합 인덱스 활용 방안
   - 인덱스 크기와 성능 영향 분석

3. **데이터 정합성 체크**
   - 주기적 정합성 검증 프로세스
   - 불일치 데이터 복구 절차
   - 감사 로그 시스템

### 7.2 성능 최적화
1. **파티셔닝 전략**
   - 시간 기반 파티셔닝 (created_at)
   - 프로젝트 기반 샤딩
   - 파티션 관리 자동화

2. **청크 최적화**
   - 문서 유형별 최적 청크 크기 분석
   - 청크 병합/분할 기준
   - 메모리 사용량 최적화

3. **임베딩 성능**
   - 벡터 차원 최적화
   - 배치 처리 크기 조정
   - 캐시 전략 수립

### 7.3 보안 강화
1. **권한 관리**
   - RBAC (Role-Based Access Control) 구현
   - 세션 기반 접근 제어
   - API 엔드포인트 보안

2. **데이터 암호화**
   - 저장 데이터 암호화 (at rest)
   - 전송 데이터 암호화 (in transit)
   - 키 관리 시스템

3. **접근 로그**
   - 상세 감사 로그
   - 이상 행동 탐지
   - 로그 보관 정책

### 7.4 기능 확장
1. **버전 관리**
   - 문서 버전 히스토리
   - 변경 사항 추적
   - 롤백 메커니즘

2. **처리 이력**
   - 상태 변경 이력
   - 처리 시간 통계
   - 오류 분석 데이터

3. **협업 기능**
   - 문서 공유 권한
   - 동시 편집 제어
   - 알림 시스템

### 7.5 운영 관리
1. **백업 전략**
   - 실시간 복제 구성
   - 지역 간 복제
   - 복구 시간 목표 (RTO) 설정

2. **데이터 보존**
   - 보존 기간 정책
   - 자동 아카이빙
   - 스토리지 계층화

3. **모니터링**
   - 실시간 알림 구성
   - 성능 메트릭 수집
   - 용량 계획
