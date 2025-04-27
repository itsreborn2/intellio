from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, UniqueConstraint, Numeric, Text, Index
from sqlalchemy.orm import relationship
from datetime import datetime

from common.models.base import Base

class EquityChangeData(Base):
    """자본변동표 데이터 모델"""
    __tablename__ = "equity_change_data"
    __table_args__ = (
        UniqueConstraint('report_id', 'company_id', 'item_id', 'year_month', name='uq_equity_change_data'),
        Index('idx_equity_change_company_year_month', 'company_id', 'year_month', postgresql_using='btree'),
        Index('idx_equity_change_item_year_month', 'item_id', 'year_month', postgresql_using='btree'),
        Index('idx_equity_change_company_item', 'company_id', 'item_id', postgresql_using='btree'),
        Index('idx_equity_change_year_month', 'year_month', postgresql_using='btree'),
        Index('idx_equity_change_company_item_year_month', 'company_id', 'item_id', 'year_month', postgresql_using='btree'),
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
    is_cumulative = Column(Boolean, default=False)  # 자본변동표는 시점 값이므로 누적 아님
    display_unit = Column(String(20), nullable=False)  # 표시 단위 (원, 백만원, 억원 등)

    
    # 관계 정의는 FinancialReport, Company, FinancialItemMapping에 역참조 정의가 있으므로 여기서는 생략
    report = relationship("FinancialReport", back_populates="equity_change_data")
    company = relationship("Company", back_populates="equity_change_data")
    item = relationship("FinancialItemMapping", back_populates="equity_change_data")
    
    def __repr__(self):
        return f"<EquityChangeData(id={self.id}, company_id={self.company_id}, item_id={self.item_id}, year_month={self.year_month})>" 