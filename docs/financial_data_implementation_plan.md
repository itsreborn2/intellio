# 재무 데이터 추출 및 저장 시스템 구현 계획

## 1. 개요

이 문서는 사업보고서, 반기보고서, 분기보고서에서 요약재무정보를 추출하여 PostgreSQL에 저장하는 시스템의 구현 계획과 진행 상황을 추적하기 위한 체크리스트를 제공합니다.

## 2. 구현 목표

- 재무 데이터 추출 파이프라인 구축
- 요약재무정보 데이터의 정규화 및 저장
- 효율적인 재무 데이터 조회 API 개발
- 향후 확장성을 고려한 데이터베이스 설계

## 3. 구현 계획 및 진행 체크리스트

> :bulb: 체크리스트 사용 방법:
> - [ ] 완료되지 않은 작업
> - [x] 완료된 작업

> :warning: **중요**: 현재 계획에서는 3.5 API 개발 단계까지만 구현합니다. 테스트 및 배포는 추후 상황에 따라 진행할 예정입니다.

### 3.1. 데이터베이스 스키마 설계 및 생성

- [x] 데이터베이스 스키마 상세 설계 문서 작성
- [x] SQLAlchemy 모델 파일 구조 설계
- [x] `Base` 모델 클래스 구현
- [x] 회사 정보 테이블 (`companies`) 모델 구현
- [x] 보고서 정보 테이블 (`financial_reports`) 모델 구현
- [x] 재무항목 매핑 테이블 (`financial_item_mappings`) 모델 구현
- [x] 항목 원본명 매핑 테이블 (`financial_item_raw_mappings`) 모델 구현
- [x] 요약재무정보 테이블 (`summary_financial_data`) 모델 구현
- [x] 데이터베이스 인덱스 생성 스크립트 작성
- [x] 데이터베이스 마이그레이션 스크립트 작성
- [x] 초기 데이터 시드 스크립트 작성 (기본 항목 매핑 등)
- [x] 마이그레이션 실행 및 검증

### 3.2. PDF 처리 모듈 개발

- [x] PDF 목차 추출 기능 구현 (fitz의 `get_toc()` 메서드 활용)
- [x] 요약재무정보 관련 목차 키워드 정의 및 페이지 식별 로직 구현
- [x] `backend\stockeasy\services\financial\data_service.py`의 `extract_revenue_breakdown_data()` 함수 패턴 적용
- [x] 요약재무정보 테이블 추출 기능 구현 (pdfplumber 활용)
- [x] 추출된 테이블 데이터 전처리 기능 구현
- [x] LLM을 활용한 테이블 구조화 프롬프트 설계
- [x] LLM 통합 및 데이터 구조화 기능 구현
- [x] 추출 오류 처리 및 로깅 시스템 구현
- [x] 추출 성능 및 정확도 테스트

### 3.3. 데이터 정규화 및 저장 로직 개발

- [x] 항목명 정규화 로직 설계
- [x] 기본 항목 매핑 데이터 준비
- [x] 자동 항목 매핑 알고리즘 개발
- [x] 수치 데이터 정규화 (단위 변환) 로직 구현
- [x] 데이터 저장 서비스 구현
- [x] 트랜잭션 처리 및 오류 처리 구현
- [x] 중복 데이터 처리 전략 구현
- [x] 데이터 정합성 검증 로직 구현

### 3.4. Redis 캐싱 시스템 구현

- [x] Redis 캐싱 전략 상세 설계
- [x] 캐싱 키 구조 정의 및 문서화
- [x] 항목 매핑 캐싱 구현
- [x] 요약재무정보 캐싱 구현
- [x] 캐시 무효화 전략 구현
- [x] 성능 테스트 및 최적화

### 3.5. API 개발

- [x] API 엔드포인트 설계
- [x] 요약재무정보 조회 API 구현
- [x] 종목별 재무정보 조회 API 구현
- [x] 기간별 재무정보 조회 API 구현
- [x] 항목별 재무정보 조회 API 구현
- [x] API 응답 캐싱 구현
- [x] API 문서화 (OpenAPI 스키마)
- [x] API 성능 테스트 및 최적화

## 4. 마일스톤

### 4.1. 마일스톤 1: 기본 인프라 구축 (1주차)
- 데이터베이스 스키마 설계 및 생성
- SQLAlchemy 모델 구현
- 기본 API 구조 설계

### 4.2. 마일스톤 2: PDF 처리 파이프라인 구축 (2주차)
- PDF 목차 추출 및 페이지 식별 구현
- 요약재무정보 테이블 추출 구현
- LLM 연동 및 데이터 구조화 구현

### 4.3. 마일스톤 3: 데이터 정규화 및 저장 (3주차)
- 항목명 정규화 로직 구현
- 데이터 저장 서비스 구현
- Redis 캐싱 시스템 구현

### 4.4. 마일스톤 4: API 개발 (4주차)
- 조회 API 개발
- API 최적화
- 성능 테스트

## 5. 인덱스 최적화 계획

자주 조회되는 데이터의 빠른 접근을 위해 다음과 같은 인덱스 최적화를 구현합니다:

### 5.1. 종목 기반 조회 최적화
```sql
-- 회사 코드 조회 (이미 설계됨)
CREATE INDEX idx_companies_code ON stockeasy.companies(company_code);

-- 종목별 재무정보 조회 최적화
CREATE INDEX idx_summary_fin_company_year_month ON stockeasy.summary_financial_data(company_id, year_month DESC);
```

### 5.2. 항목 기반 조회 최적화
```sql
-- 특정 항목 시계열 조회 최적화
CREATE INDEX idx_summary_fin_item_year_month ON stockeasy.summary_financial_data(item_id, year_month DESC);

-- 특정 항목과 종목 조회 (자주 사용됨)
CREATE INDEX idx_summary_fin_item_company ON stockeasy.summary_financial_data(item_id, company_id);
```

### 5.3. 기간 기반 조회 최적화
```sql
-- 기간별 조회 최적화 (이미 설계됨)
CREATE INDEX idx_summary_fin_year_month ON stockeasy.summary_financial_data(year_month DESC);

-- 특정 연도 조회 최적화 (연도별 집계시)
CREATE INDEX idx_summary_fin_year ON stockeasy.summary_financial_data((year_month / 100));
```

### 5.4. 복합 쿼리 최적화
```sql
-- 종목+항목+기간 조회 (가장 자주 사용되는 쿼리 패턴)
CREATE INDEX idx_summary_fin_company_item_year_month 
  ON stockeasy.summary_financial_data(company_id, item_id, year_month DESC);

-- 항목 매핑 테이블 조회 최적화
CREATE INDEX idx_item_mappings_category ON stockeasy.financial_item_mappings(category, is_active);
```

## 6. 최적화된 쿼리 패턴

### 6.1. 특정 종목의 최근 요약재무정보 조회
```sql
-- 캐시 미스 시 사용할 쿼리
SELECT c.company_code, c.company_name, fim.standard_name, fim.item_code, 
       sfd.year_month, sfd.value, sfd.display_unit
FROM stockeasy.summary_financial_data sfd
JOIN stockeasy.companies c ON sfd.company_id = c.id
JOIN stockeasy.financial_item_mappings fim ON sfd.item_id = fim.id
WHERE c.company_code = '005930' 
ORDER BY sfd.year_month DESC
LIMIT 20;
```

### 6.2. 특정 항목의 여러 종목 비교
```sql
-- 매출액 항목의 여러 종목 비교 (최근 분기)
SELECT c.company_code, c.company_name, sfd.year_month, sfd.value
FROM stockeasy.summary_financial_data sfd
JOIN stockeasy.companies c ON sfd.company_id = c.id
JOIN stockeasy.financial_item_mappings fim ON sfd.item_id = fim.id
WHERE fim.item_code = 'revenue'
  AND sfd.year_month = (SELECT MAX(year_month) FROM stockeasy.summary_financial_data)
  AND c.company_code IN ('005930', '000660', '035420')
ORDER BY sfd.value DESC;
```

### 6.3. 시계열 데이터 조회
```sql
-- 특정 종목의 특정 항목 시계열 데이터
SELECT sfd.year_month, sfd.value
FROM stockeasy.summary_financial_data sfd
JOIN stockeasy.companies c ON sfd.company_id = c.id
JOIN stockeasy.financial_item_mappings fim ON sfd.item_id = fim.id
WHERE c.company_code = '005930'
  AND fim.item_code = 'revenue'
  AND sfd.year_month >= 202000
ORDER BY sfd.year_month;
```

## 7. 위험 요소 및 대응 계획

| 위험 요소 | 영향도 | 가능성 | 대응 계획 |
|----------|--------|--------|----------|
| PDF 구조가 예상과 다른 경우 | 높음 | 중간 | 다양한 보고서 샘플을 수집하여 테스트, 예외 처리 로직 강화 |
| 항목명 정규화 정확도 부족 | 높음 | 높음 | 수동 매핑 테이블 구축, LLM 프롬프트 최적화 |
| 대용량 데이터 처리 성능 이슈 | 중간 | 중간 | 인덱싱 최적화, 캐싱 전략 개선, 비동기 처리 도입 |
| API 응답 시간 지연 | 중간 | 낮음 | 캐싱 적용, 쿼리 최적화, N+1 문제 해결 |
| 데이터 품질 저하 | 높음 | 중간 | 데이터 검증 로직 강화, 모니터링 시스템 구축 |

## 8. 작업 진행 상황 보고

### 8.1. 진행 상황 요약

| 마일스톤 | 계획 완료일 | 실제 완료일 | 진행률 | 특이사항 |
|---------|------------|------------|--------|---------|
| 마일스톤 1 | 2023-09-01 | 2023-09-01 | 100% | 데이터베이스 스키마 설계 및 모델 구현 완료 |
| 마일스톤 2 | 2023-09-08 | 2023-09-08 | 100% | PDF 처리 파이프라인 구축 완료 |
| 마일스톤 3 | 2023-09-15 | 2023-09-15 | 100% | 데이터 정규화 및 저장 로직 구현 완료 |
| 마일스톤 4 | 2023-09-22 | 2023-09-22 | 100% | API 개발 및 최적화 완료 |

### 8.2. 주간 진행 보고

#### 1주차 (2023-08-28 ~ 2023-09-01)
- 완료된 작업:
  - 데이터베이스 스키마 설계 문서 작성
  - SQLAlchemy 모델 구현
  - 인덱스 설계 및 스크립트 작성
- 진행 중인 작업:
  - 없음
- 다음 주 계획:
  - PDF 처리 모듈 개발
- 이슈 및 리스크:
  - Base 모델 클래스 충돌 이슈 발견 (해결됨)