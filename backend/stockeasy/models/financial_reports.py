from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from common.models.base import Base


class FinancialReport(Base):
    """재무 보고서 정보 모델"""
    __tablename__ = "financial_reports"
    __table_args__ = (
        UniqueConstraint('company_id', 'report_year', 'report_quarter', name='uq_company_report'),
        {"schema": "stockeasy"}
    )
    
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("stockeasy.companies.id"), nullable=False)
    report_type = Column(String(20), nullable=False)  # annual, semi, quarter
    report_year = Column(Integer, nullable=False)
    report_quarter = Column(Integer)  # 연간은 null, 분기는 1,2,3,4
    year_month = Column(Integer, nullable=False, index=True)  # YYYYMM 형식: 202403, 202406, 202409, 202412
    file_path = Column(String(255))  # PDF 파일 경로
    processed = Column(Boolean, default=False)

    
    # 관계 정의
    company = relationship("Company", back_populates="financial_reports")
    summary_data = relationship("SummaryFinancialData", back_populates="report", cascade="all, delete-orphan")
    income_statement_data = relationship("IncomeStatementData", back_populates="report", cascade="all, delete-orphan")
    balance_sheet_data = relationship("BalanceSheetData", back_populates="report", cascade="all, delete-orphan")
    cash_flow_data = relationship("CashFlowData", back_populates="report", cascade="all, delete-orphan")
    equity_change_data = relationship("EquityChangeData", back_populates="report", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<FinancialReport(id={self.id}, company_id={self.company_id}, year={self.report_year}, quarter={self.report_quarter})>" 