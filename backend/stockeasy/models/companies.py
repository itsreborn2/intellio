from sqlalchemy import Column, String, Boolean, Integer, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from common.models.base import Base


class Company(Base):
    """회사 정보 모델"""
    __tablename__ = "companies"
    __table_args__ = {"schema": "stockeasy"}
    
    id = Column(Integer, primary_key=True, index=True)
    company_code = Column(String(20), unique=True, nullable=False, index=True)
    company_name = Column(String(100), nullable=False)
    market_type = Column(String(20))  # KOSPI, KOSDAQ 등
    sector = Column(String(100))  # 업종
    is_active = Column(Boolean, default=True)
    
    # 관계 정의
    financial_reports = relationship("FinancialReport", back_populates="company", cascade="all, delete-orphan")
    summary_financial_data = relationship("SummaryFinancialData", back_populates="company", cascade="all, delete-orphan")
    income_statement_data = relationship("IncomeStatementData", back_populates="company", cascade="all, delete-orphan")
    balance_sheet_data = relationship("BalanceSheetData", back_populates="company", cascade="all, delete-orphan")
    cash_flow_data = relationship("CashFlowData", back_populates="company", cascade="all, delete-orphan")
    equity_change_data = relationship("EquityChangeData", back_populates="company", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Company(id={self.id}, code={self.company_code}, name={self.company_name})>" 