"""
주식 관련 데이터 모델
"""
from datetime import datetime, date
from typing import Optional
from decimal import Decimal

from sqlalchemy import Column, Integer, String, Date, DateTime, Numeric, BigInteger, Index, UniqueConstraint, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.postgresql import UUID
import uuid

Base = declarative_base()


class StockSymbol(Base):
    """종목코드 <-> 종목명 매핑 테이블"""
    __tablename__ = "stock_symbols"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), unique=True, nullable=False, index=True, comment="종목코드")
    name = Column(String(100), nullable=False, comment="종목명")
    market = Column(String(20), nullable=False, comment="시장구분 (KOSPI, KOSDAQ, etc.)")
    sector = Column(String(50), comment="업종")
    listing_date = Column(Date, comment="상장일")
    is_active = Column(Boolean, default=True, comment="활성화 여부")
    created_at = Column(DateTime, default=datetime.utcnow, comment="생성일시")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="수정일시")
    
    __table_args__ = (
        Index('idx_symbol_market', 'symbol', 'market'),
        Index('idx_name', 'name'),
        Index('idx_is_active', 'is_active'),
    )


class StockPrice(Base):
    """종목 기본정보 및 가격 데이터"""
    __tablename__ = "stock_prices"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, index=True, comment="종목코드")
    name = Column(String(100), nullable=False, comment="종목명")
    trade_date = Column(Date, nullable=False, index=True, comment="거래일자")
    
    # OHLCV 데이터
    open_price = Column(Numeric(12, 2), comment="시가")
    high_price = Column(Numeric(12, 2), comment="고가")
    low_price = Column(Numeric(12, 2), comment="저가")
    close_price = Column(Numeric(12, 2), comment="종가")
    volume = Column(BigInteger, comment="거래량")
    trading_value = Column(BigInteger, comment="거래대금")
    
    # 수정주가 관련
    adj_factor = Column(Numeric(10, 6), default=1.0, comment="수정계수")
    adj_close_price = Column(Numeric(12, 2), comment="수정종가")
    
    # 주식 기본정보
    total_shares = Column(BigInteger, comment="총주식수")
    market_cap = Column(BigInteger, comment="시가총액")
    listed_shares = Column(BigInteger, comment="상장주식수")
    floating_shares = Column(BigInteger, comment="유통주식수")
    floating_ratio = Column(Numeric(5, 2), comment="유통비율(%)")
    
    # 주가 지표
    per = Column(Numeric(8, 2), comment="PER")
    pbr = Column(Numeric(8, 2), comment="PBR")
    eps = Column(Numeric(10, 2), comment="EPS")
    bps = Column(Numeric(10, 2), comment="BPS")
    
    # 메타데이터
    created_at = Column(DateTime, default=datetime.utcnow, comment="생성일시")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="수정일시")
    
    __table_args__ = (
        UniqueConstraint('symbol', 'trade_date', name='uq_symbol_trade_date'),
        Index('idx_symbol_date', 'symbol', 'trade_date'),
        Index('idx_trade_date', 'trade_date'),
        Index('idx_market_cap', 'market_cap'),
    )


class StockSupplyDemand(Base):
    """주식 수급 데이터"""
    __tablename__ = "stock_supply_demand"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, index=True, comment="종목코드")
    trade_date = Column(Date, nullable=False, index=True, comment="거래일자")
    
    # 수급 데이터 (단위: 천주, 양수는 순매수, 음수는 순매도)
    foreign_net = Column(BigInteger, comment="외국인 순매수")
    institution_net = Column(BigInteger, comment="기관계 순매수")
    
    # 기관 세부
    financial_investment_net = Column(BigInteger, comment="금융투자 순매수")
    insurance_net = Column(BigInteger, comment="보험 순매수")
    investment_trust_net = Column(BigInteger, comment="투신 순매수")
    other_financial_net = Column(BigInteger, comment="기타금융기관 순매수")
    bank_net = Column(BigInteger, comment="은행 순매수")
    pension_net = Column(BigInteger, comment="연기금 순매수")
    private_fund_net = Column(BigInteger, comment="사모펀드 순매수")
    government_net = Column(BigInteger, comment="국가(지자체) 순매수")
    other_corporate_net = Column(BigInteger, comment="기타법인 순매수")
    
    # 종합
    foreign_domestic_net = Column(BigInteger, comment="내외국인 순매수")
    program_net = Column(BigInteger, comment="프로그램 순매수")
    
    # 거래량 정보
    total_volume = Column(BigInteger, comment="총 거래량")
    foreign_volume = Column(BigInteger, comment="외국인 거래량")
    institution_volume = Column(BigInteger, comment="기관 거래량")
    individual_volume = Column(BigInteger, comment="개인 거래량")
    
    # 거래대금 정보
    total_value = Column(BigInteger, comment="총 거래대금")
    foreign_value = Column(BigInteger, comment="외국인 거래대금")
    institution_value = Column(BigInteger, comment="기관 거래대금")
    individual_value = Column(BigInteger, comment="개인 거래대금")
    
    # 메타데이터
    created_at = Column(DateTime, default=datetime.utcnow, comment="생성일시")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="수정일시")
    
    __table_args__ = (
        UniqueConstraint('symbol', 'trade_date', name='uq_supply_demand_symbol_date'),
        Index('idx_supply_demand_symbol_date', 'symbol', 'trade_date'),
        Index('idx_foreign_net', 'foreign_net'),
        Index('idx_institution_net', 'institution_net'),
    )


class StockRealtime(Base):
    """실시간 주식 데이터 (최근 데이터만 DB 저장, 주로 Redis 사용)"""
    __tablename__ = "stock_realtime"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, index=True, comment="종목코드")
    
    # 현재가 정보
    current_price = Column(Numeric(12, 2), comment="현재가")
    change_amount = Column(Numeric(12, 2), comment="전일대비 금액")
    change_rate = Column(Numeric(5, 2), comment="전일대비 비율(%)")
    
    # 거래 정보
    volume = Column(BigInteger, comment="거래량")
    trading_value = Column(BigInteger, comment="거래대금")
    
    # 호가 정보
    bid_price = Column(Numeric(12, 2), comment="매수호가")
    ask_price = Column(Numeric(12, 2), comment="매도호가")
    bid_volume = Column(BigInteger, comment="매수호가량")
    ask_volume = Column(BigInteger, comment="매도호가량")
    
    # 당일 고저가
    day_high = Column(Numeric(12, 2), comment="당일 고가")
    day_low = Column(Numeric(12, 2), comment="당일 저가")
    
    # 시간 정보
    last_update = Column(DateTime, nullable=False, comment="마지막 업데이트 시간")
    trade_time = Column(DateTime, comment="체결시간")
    
    __table_args__ = (
        Index('idx_realtime_symbol_update', 'symbol', 'last_update'),
        Index('idx_last_update', 'last_update'),
    )
