# 재무 데이터 추출 및 저장 시스템 설계

## 1. 개요

이 문서는 사업보고서, 반기보고서, 분기보고서에서 재무 데이터를 추출하여 PostgreSQL 데이터베이스에 저장하는 시스템의 구조와 설계를 설명합니다. 현재 구현 단계에서는 요약재무정보 추출 및 저장에 초점을 맞추고 있으며, 향후 재무상태표, 손익계산서, 현금흐름표 등으로 확장할 계획입니다.

## 2. 데이터 흐름도

```
PDF 보고서 → fitz(목차 페이지 식별) → pdfplumber(데이터 추출) → LLM(데이터 구조화) → PostgreSQL(정규화 저장)
```

## 3. 데이터베이스 스키마 설계

모든 테이블은 `stockeasy` 스키마 내에 생성됩니다.

### 3.1. 회사 정보 테이블 (stockeasy.companies)

| 컬럼명 | 데이터 타입 | 설명 | 제약조건 |
|-------|-------------|------|---------|
| id | SERIAL | 내부 식별자 | PRIMARY KEY |
| company_code | VARCHAR(20) | 종목코드 (005930 등) | NOT NULL, UNIQUE |
| company_name | VARCHAR(100) | 회사명 | NOT NULL |
| market_type | VARCHAR(20) | 시장구분 (KOSPI, KOSDAQ 등) | - |
| sector | VARCHAR(100) | 업종 | - |
| is_active | BOOLEAN | 활성 상태 | DEFAULT TRUE |
| created_at | TIMESTAMP | 생성 시간 | DEFAULT CURRENT_TIMESTAMP |
| updated_at | TIMESTAMP | 수정 시간 | DEFAULT CURRENT_TIMESTAMP |

### 3.2. 보고서 정보 테이블 (stockeasy.financial_reports)

| 컬럼명 | 데이터 타입 | 설명 | 제약조건 |
|-------|-------------|------|---------|
| id | SERIAL | 내부 식별자 | PRIMARY KEY |
| company_id | INTEGER | 회사 ID | REFERENCES companies(id), NOT NULL |
| report_type | VARCHAR(20) | 보고서 유형 (annual, semi, quarter) | NOT NULL |
| report_year | INTEGER | 보고서 연도 | NOT NULL |
| report_quarter | INTEGER | 분기 (NULL, 1, 2, 3, 4) | - |
| year_month | INTEGER | YYYYMM 형식 (202403 등) | NOT NULL |
| file_path | VARCHAR(255) | PDF 파일 경로 | - |
| processed | BOOLEAN | 처리 완료 여부 | DEFAULT FALSE |
| created_at | TIMESTAMP | 생성 시간 | DEFAULT CURRENT_TIMESTAMP |
| updated_at | TIMESTAMP | 수정 시간 | DEFAULT CURRENT_TIMESTAMP |

```sql
UNIQUE (company_id, report_year, report_quarter)
```

### 3.3. 재무항목 정규화 테이블 (stockeasy.financial_item_mappings)

| 컬럼명 | 데이터 타입 | 설명 | 제약조건 |
|-------|-------------|------|---------|
| id | SERIAL | 내부 식별자 | PRIMARY KEY |
| item_code | VARCHAR(50) | 표준 항목 코드 | NOT NULL, UNIQUE |
| category | VARCHAR(50) | 항목 분류 (요약재무정보, 재무상태표 등) | NOT NULL |
| standard_name | VARCHAR(100) | 표준화된 이름 | NOT NULL |
| description | TEXT | 항목 설명 | - |
| display_order | INTEGER | 표시 순서 | - |
| is_active | BOOLEAN | 활성 상태 | DEFAULT TRUE |
| created_at | TIMESTAMP | 생성 시간 | DEFAULT CURRENT_TIMESTAMP |
| updated_at | TIMESTAMP | 수정 시간 | DEFAULT CURRENT_TIMESTAMP |

### 3.4. 항목 원본명 매핑 테이블 (stockeasy.financial_item_raw_mappings)

| 컬럼명 | 데이터 타입 | 설명 | 제약조건 |
|-------|-------------|------|---------|
| id | SERIAL | 내부 식별자 | PRIMARY KEY |
| mapping_id | INTEGER | 매핑 ID | REFERENCES financial_item_mappings(id), NOT NULL |
| raw_name | VARCHAR(200) | 원본 항목명 | NOT NULL |
| created_at | TIMESTAMP | 생성 시간 | DEFAULT CURRENT_TIMESTAMP |
| updated_at | TIMESTAMP | 수정 시간 | DEFAULT CURRENT_TIMESTAMP |

```sql
UNIQUE (raw_name, mapping_id)
```

### 3.5. 요약재무정보 테이블 (stockeasy.summary_financial_data)

| 컬럼명 | 데이터 타입 | 설명 | 제약조건 |
|-------|-------------|------|---------|
| id | BIGSERIAL | 내부 식별자 | PRIMARY KEY |
| report_id | INTEGER | 보고서 ID | REFERENCES financial_reports(id), NOT NULL |
| company_id | INTEGER | 회사 ID | REFERENCES companies(id), NOT NULL |
| item_id | INTEGER | 항목 ID | REFERENCES financial_item_mappings(id), NOT NULL |
| year_month | INTEGER | YYYYMM 형식 | NOT NULL |
| value | DECIMAL(30, 2) | 값 (원 단위) | NOT NULL |
| display_unit | VARCHAR(20) | 표시 단위 (백만원, 억원 등) | NOT NULL |
| created_at | TIMESTAMP | 생성 시간 | DEFAULT CURRENT_TIMESTAMP |
| updated_at | TIMESTAMP | 수정 시간 | DEFAULT CURRENT_TIMESTAMP |

```sql
UNIQUE (report_id, company_id, item_id, year_month)
```

## 4. 인덱스 설계

성능 최적화를 위한 인덱스 설계:

```sql
-- 회사 조회 인덱스
CREATE INDEX idx_companies_code ON stockeasy.companies(company_code);

-- 보고서 조회 인덱스
CREATE INDEX idx_financial_reports_company_year_month ON stockeasy.financial_reports(company_id, year_month);
CREATE INDEX idx_financial_reports_year_month ON stockeasy.financial_reports(year_month);

-- 요약재무정보 조회 인덱스
CREATE INDEX idx_summary_fin_company_item ON stockeasy.summary_financial_data(company_id, item_id);
CREATE INDEX idx_summary_fin_year_month ON stockeasy.summary_financial_data(year_month);
CREATE INDEX idx_summary_fin_company_year_month ON stockeasy.summary_financial_data(company_id, year_month);
CREATE INDEX idx_summary_fin_item_year_month ON stockeasy.summary_financial_data(item_id, year_month);
```

## 5. SQLAlchemy 모델 설계

```python
# stockeasy/models/companies.py
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from stockeasy.models.base import Base

class Company(Base):
    __tablename__ = "companies"
    __table_args__ = {"schema": "stockeasy"}
    
    id = Column(Integer, primary_key=True, index=True)
    company_code = Column(String(20), unique=True, nullable=False)
    company_name = Column(String(100), nullable=False)
    market_type = Column(String(20))
    sector = Column(String(100))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    reports = relationship("FinancialReport", back_populates="company")
    summary_data = relationship("SummaryFinancialData", back_populates="company")

# stockeasy/models/financial_reports.py
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from stockeasy.models.base import Base

class FinancialReport(Base):
    __tablename__ = "financial_reports"
    __table_args__ = (
        UniqueConstraint('company_id', 'report_year', 'report_quarter', name='uq_company_report'),
        {"schema": "stockeasy"}
    )
    
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("stockeasy.companies.id"), nullable=False)
    report_type = Column(String(20), nullable=False)
    report_year = Column(Integer, nullable=False)
    report_quarter = Column(Integer)
    year_month = Column(Integer, nullable=False)
    file_path = Column(String(255))
    processed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    company = relationship("Company", back_populates="reports")
    summary_data = relationship("SummaryFinancialData", back_populates="report")

# stockeasy/models/financial_data.py
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, UniqueConstraint, Numeric, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from stockeasy.models.base import Base

class FinancialItemMapping(Base):
    __tablename__ = "financial_item_mappings"
    __table_args__ = {"schema": "stockeasy"}
    
    id = Column(Integer, primary_key=True, index=True)
    item_code = Column(String(50), unique=True, nullable=False)
    category = Column(String(50), nullable=False)
    standard_name = Column(String(100), nullable=False)
    description = Column(Text)
    display_order = Column(Integer)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    raw_mappings = relationship("FinancialItemRawMapping", back_populates="mapping")
    summary_data = relationship("SummaryFinancialData", back_populates="item")

class FinancialItemRawMapping(Base):
    __tablename__ = "financial_item_raw_mappings"
    __table_args__ = (
        UniqueConstraint('raw_name', 'mapping_id', name='uq_raw_name_mapping'),
        {"schema": "stockeasy"}
    )
    
    id = Column(Integer, primary_key=True, index=True)
    mapping_id = Column(Integer, ForeignKey("stockeasy.financial_item_mappings.id"), nullable=False)
    raw_name = Column(String(200), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    mapping = relationship("FinancialItemMapping", back_populates="raw_mappings")

class SummaryFinancialData(Base):
    __tablename__ = "summary_financial_data"
    __table_args__ = (
        UniqueConstraint('report_id', 'company_id', 'item_id', 'year_month', name='uq_summary_data'),
        {"schema": "stockeasy"}
    )
    
    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(Integer, ForeignKey("stockeasy.financial_reports.id"), nullable=False)
    company_id = Column(Integer, ForeignKey("stockeasy.companies.id"), nullable=False)
    item_id = Column(Integer, ForeignKey("stockeasy.financial_item_mappings.id"), nullable=False)
    year_month = Column(Integer, nullable=False)
    value = Column(Numeric(30, 2), nullable=False)
    display_unit = Column(String(20), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    report = relationship("FinancialReport", back_populates="summary_data")
    company = relationship("Company", back_populates="summary_data")
    item = relationship("FinancialItemMapping", back_populates="summary_data")
```

## 6. 캐싱 전략

Redis를 사용하여 다음 데이터를 캐싱:

1. 자주 조회되는 종목의 최신 요약재무정보
2. 항목 매핑 정보 (항목명 정규화)
3. 인기 종목 및 항목의 시계열 데이터

캐싱 키 구조:
- `stockeasy:summary:{company_code}:{year_month}` - 특정 기업, 특정 기간의 요약재무정보
- `stockeasy:item_mappings` - 항목 매핑 전체 정보
- `stockeasy:raw_name_mapping:{raw_name}` - 원본 항목명에 대한 매핑 정보

## 7. 확장성 고려사항

현재는 요약재무정보만 구현하지만, 향후 다음 테이블이 추가될 예정:

1. 재무상태표 테이블 (stockeasy.balance_sheet_data)
2. 손익계산서 테이블 (stockeasy.income_statement_data)
3. 현금흐름표 테이블 (stockeasy.cash_flow_data)

각 테이블은 요약재무정보 테이블과 유사한 구조를 가지며, 항목 정규화를 위해 동일한 매핑 테이블을 활용합니다. 