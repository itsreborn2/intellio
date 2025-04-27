from sqlalchemy import Column, Integer, String, Boolean, Text, ForeignKey, UniqueConstraint, Numeric, Index
from sqlalchemy.orm import relationship
from datetime import datetime
from common.models.base import Base


class FinancialItemMapping(Base):
    """재무 항목 매핑 모델 (표준화된 항목 정의)"""
    __tablename__ = "financial_item_mappings"
    __table_args__ = {"schema": "stockeasy"}
    
    id = Column(Integer, primary_key=True, index=True)
    item_code = Column(String(200), unique=True, nullable=False, index=True)
    category = Column(String(100), nullable=False, index=True)  # 요약재무정보, 재무상태표, 손익계산서, 현금흐름표
    standard_name = Column(String(200), nullable=False)
    description = Column(Text)
    display_order = Column(Integer)
    is_active = Column(Boolean, default=True)

    
    # 관계 정의
    raw_mappings = relationship("FinancialItemRawMapping", back_populates="mapping", cascade="all, delete-orphan")
    summary_data = relationship("SummaryFinancialData", back_populates="item")
    income_statement_data = relationship("IncomeStatementData", back_populates="item")
    balance_sheet_data = relationship("BalanceSheetData", back_populates="item")
    cash_flow_data = relationship("CashFlowData", back_populates="item")
    equity_change_data = relationship("EquityChangeData", back_populates="item")
    
    def __repr__(self):
        return f"<FinancialItemMapping(id={self.id}, item_code={self.item_code}, standard_name={self.standard_name})>"


class FinancialItemRawMapping(Base):
    """재무 항목 원본명 매핑 모델 (원본 항목명과 표준 항목 간 매핑)"""
    __tablename__ = "financial_item_raw_mappings"
    __table_args__ = (
        UniqueConstraint('raw_name', 'mapping_id', name='uq_raw_name_mapping'),
        {"schema": "stockeasy"}
    )
    
    id = Column(Integer, primary_key=True, index=True)
    mapping_id = Column(Integer, ForeignKey("stockeasy.financial_item_mappings.id"), nullable=False)
    raw_name = Column(String(200), nullable=False, index=True)
    
    # 관계 정의
    mapping = relationship("FinancialItemMapping", back_populates="raw_mappings")
    
    def __repr__(self):
        return f"<FinancialItemRawMapping(id={self.id}, raw_name={self.raw_name})>"


class SummaryFinancialData(Base):
    """요약재무정보 데이터 모델"""
    __tablename__ = "summary_financial_data"
    __table_args__ = (
        UniqueConstraint('report_id', 'company_id', 'item_id', 'year_month', name='uq_summary_data'),
        Index('idx_summary_fin_company_year_month', 'company_id', 'year_month', postgresql_using='btree'),
        Index('idx_summary_fin_item_year_month', 'item_id', 'year_month', postgresql_using='btree'),
        Index('idx_summary_fin_company_item', 'company_id', 'item_id', postgresql_using='btree'),
        Index('idx_summary_fin_year_month', 'year_month', postgresql_using='btree'),
        Index('idx_summary_fin_company_item_year_month', 'company_id', 'item_id', 'year_month', postgresql_using='btree'),
        {"schema": "stockeasy"}
    )
    
    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(Integer, ForeignKey("stockeasy.financial_reports.id"), nullable=False)
    company_id = Column(Integer, ForeignKey("stockeasy.companies.id"), nullable=False)
    item_id = Column(Integer, ForeignKey("stockeasy.financial_item_mappings.id"), nullable=False)
    year_month = Column(Integer, nullable=False)  # YYYYMM 형식
    value = Column(Numeric(30, 2), nullable=False)  # 원래 저장하던 값 (호환성 유지)
    cumulative_value = Column(Numeric(30, 2))  # 누적 값
    period_value = Column(Numeric(30, 2))  # 특정 기간만의 값
    is_cumulative = Column(Boolean, default=False)  # 누적 값 여부
    statement_type = Column(String(30))  # 재무제표 타입 (재무상태표, 손익계산서, 현금흐름표)
    display_unit = Column(String(20), nullable=False)  # 표시 단위 (원, 백만원, 억원 등)
    
    # 관계 정의
    report = relationship("FinancialReport", back_populates="summary_data")
    company = relationship("Company", back_populates="summary_financial_data")
    item = relationship("FinancialItemMapping", back_populates="summary_data")
    
    def __repr__(self):
        return f"<SummaryFinancialData(id={self.id}, company_id={self.company_id}, item_id={self.item_id}, year_month={self.year_month})>" 