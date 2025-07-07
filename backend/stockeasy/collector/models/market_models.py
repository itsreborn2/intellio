"""
시장 및 ETF 관련 데이터 모델
"""
from datetime import datetime, date
from typing import Optional
from decimal import Decimal

from sqlalchemy import Column, Integer, String, Date, DateTime, Numeric, BigInteger, Index, UniqueConstraint, Boolean, Text, JSON
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class ETF(Base):
    """ETF 기본 정보"""
    __tablename__ = "etfs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), unique=True, nullable=False, index=True, comment="ETF 코드")
    name = Column(String(100), nullable=False, comment="ETF 명")
    
    # ETF 기본 정보
    net_asset_value = Column(Numeric(12, 2), comment="순자산가치(NAV)")
    total_assets = Column(BigInteger, comment="순자산총액")
    expense_ratio = Column(Numeric(5, 4), comment="운용보수율(%)")
    tracking_error = Column(Numeric(5, 4), comment="추적오차(%)")
    
    # 분류 정보
    asset_class = Column(String(50), comment="자산군 (주식, 채권, 원자재 등)")
    region = Column(String(50), comment="투자지역")
    sector = Column(String(50), comment="섹터")
    strategy = Column(String(100), comment="투자전략")
    
    # 기초지수 정보
    benchmark_index = Column(String(100), comment="기초지수명")
    index_provider = Column(String(50), comment="지수제공업체")
    
    # 운용사 정보
    management_company = Column(String(100), comment="운용사")
    inception_date = Column(Date, comment="설정일")
    
    # 분배 정보
    distribution_frequency = Column(String(20), comment="분배주기")
    distribution_yield = Column(Numeric(5, 2), comment="분배수익률(%)")
    
    is_active = Column(Boolean, default=True, comment="활성화 여부")
    created_at = Column(DateTime, default=datetime.utcnow, comment="생성일시")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="수정일시")
    
    __table_args__ = (
        Index('idx_etf_asset_class', 'asset_class'),
        Index('idx_etf_region', 'region'),
        Index('idx_etf_management_company', 'management_company'),
    )


class ETFComponent(Base):
    """ETF 구성종목"""
    __tablename__ = "etf_components"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    etf_symbol = Column(String(20), nullable=False, index=True, comment="ETF 코드")
    stock_code = Column(String(20), nullable=False, index=True, comment="구성종목 코드")
    stock_name = Column(String(100), comment="구성종목명")
    
    # 구성 정보
    weight = Column(Numeric(8, 4), comment="비중(%)")
    shares = Column(BigInteger, comment="보유주식수")
    market_value = Column(BigInteger, comment="평가금액")
    
    # 업데이트 정보
    update_date = Column(Date, nullable=False, index=True, comment="업데이트 일자")
    created_at = Column(DateTime, default=datetime.utcnow, comment="생성일시")
    
    __table_args__ = (
        UniqueConstraint('etf_symbol', 'stock_code', 'update_date', name='uq_etf_component_date'),
        Index('idx_etf_component_symbol', 'etf_symbol', 'stock_code'),
        Index('idx_component_weight', 'weight'),
    )


class MarketIndex(Base):
    """시장 지수 정보"""
    __tablename__ = "market_indices"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    index_code = Column(String(20), unique=True, nullable=False, index=True, comment="지수코드")
    index_name = Column(String(100), nullable=False, comment="지수명")
    
    # 분류 정보
    market = Column(String(20), comment="시장구분")
    category = Column(String(50), comment="지수 카테고리")
    base_date = Column(Date, comment="기준일")
    base_value = Column(Numeric(10, 2), comment="기준값")
    
    # 구성 정보
    component_count = Column(Integer, comment="구성종목수")
    market_cap = Column(BigInteger, comment="시가총액")
    
    description = Column(Text, comment="지수설명")
    provider = Column(String(50), comment="지수제공업체")
    
    is_active = Column(Boolean, default=True, comment="활성화 여부")
    created_at = Column(DateTime, default=datetime.utcnow, comment="생성일시")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="수정일시")


class MarketIndexPrice(Base):
    """시장 지수 가격 데이터"""
    __tablename__ = "market_index_prices"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    index_code = Column(String(20), nullable=False, index=True, comment="지수코드")
    trade_date = Column(Date, nullable=False, index=True, comment="거래일자")
    
    # 지수 가격 정보
    open_value = Column(Numeric(12, 2), comment="시가")
    high_value = Column(Numeric(12, 2), comment="고가")
    low_value = Column(Numeric(12, 2), comment="저가")
    close_value = Column(Numeric(12, 2), comment="종가")
    
    # 변동 정보
    change_amount = Column(Numeric(12, 2), comment="전일대비 변동")
    change_rate = Column(Numeric(5, 2), comment="전일대비 변동률(%)")
    
    # 거래 정보
    volume = Column(BigInteger, comment="거래량")
    trading_value = Column(BigInteger, comment="거래대금")
    
    created_at = Column(DateTime, default=datetime.utcnow, comment="생성일시")
    
    __table_args__ = (
        UniqueConstraint('index_code', 'trade_date', name='uq_index_trade_date'),
        Index('idx_index_date', 'index_code', 'trade_date'),
    )


class MarketStatus(Base):
    """시장 상태 정보"""
    __tablename__ = "market_status"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    market = Column(String(20), nullable=False, index=True, comment="시장구분")
    trade_date = Column(Date, nullable=False, index=True, comment="거래일자")
    
    # 시장 상태
    market_status = Column(String(20), comment="시장상태 (개장, 폐장, 휴장)")
    trading_hours = Column(JSON, comment="거래시간 정보")
    
    # 시장 통계
    total_stocks = Column(Integer, comment="총 상장종목수")
    trading_stocks = Column(Integer, comment="거래종목수")
    rising_stocks = Column(Integer, comment="상승종목수")
    falling_stocks = Column(Integer, comment="하락종목수")
    unchanged_stocks = Column(Integer, comment="보합종목수")
    
    # 거래 통계
    total_volume = Column(BigInteger, comment="총 거래량")
    total_value = Column(BigInteger, comment="총 거래대금")
    
    # 외국인 정보
    foreign_net_volume = Column(BigInteger, comment="외국인 순매수량")
    foreign_net_value = Column(BigInteger, comment="외국인 순매수대금")
    
    # 기관 정보
    institution_net_volume = Column(BigInteger, comment="기관 순매수량")
    institution_net_value = Column(BigInteger, comment="기관 순매수대금")
    
    created_at = Column(DateTime, default=datetime.utcnow, comment="생성일시")
    
    __table_args__ = (
        UniqueConstraint('market', 'trade_date', name='uq_market_status_date'),
        Index('idx_market_trade_date', 'market', 'trade_date'),
    )


class TradingCalendar(Base):
    """거래일 캘린더"""
    __tablename__ = "trading_calendar"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    trade_date = Column(Date, unique=True, nullable=False, index=True, comment="일자")
    
    # 거래일 여부
    is_trading_day = Column(Boolean, nullable=False, comment="거래일 여부")
    market = Column(String(20), default="ALL", comment="적용 시장")
    
    # 휴장 사유
    holiday_name = Column(String(100), comment="휴일명")
    holiday_type = Column(String(50), comment="휴일 구분")
    
    # 단축거래일 정보
    is_short_trading = Column(Boolean, default=False, comment="단축거래일 여부")
    trading_hours = Column(JSON, comment="거래시간 (단축거래 시)")
    
    created_at = Column(DateTime, default=datetime.utcnow, comment="생성일시")
    
    __table_args__ = (
        Index('idx_trading_calendar_market', 'market', 'trade_date'),
        Index('idx_is_trading_day', 'is_trading_day'),
    ) 