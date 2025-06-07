"""
TimescaleDB용 SQLAlchemy 모델 정의
시계열 데이터를 위한 하이퍼테이블 모델들
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, String, Numeric, BigInteger, Index, Boolean, Text, Integer
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.ext.declarative import declarative_base


# TimescaleDB 전용 Base 클래스
TimescaleBase = declarative_base()


class StockPrice(TimescaleBase):
    """주가 데이터 (키움 API ka10081 - 주식일봉차트조회)"""
    __tablename__ = "stock_prices"
    
    time = Column(TIMESTAMP(timezone=True), primary_key=True, nullable=False, comment="시간 (UTC)")
    symbol = Column(String(10), primary_key=True, nullable=False, comment="종목코드")
    interval_type = Column(String(10), primary_key=True, nullable=False, default="1d", comment="봉 타입 (1m, 5m, 1d)")
    
    # OHLCV 기본 데이터
    open = Column(Numeric(12,2), comment="시가")
    high = Column(Numeric(12,2), comment="고가")
    low = Column(Numeric(12,2), comment="저가")
    close = Column(Numeric(12,2), comment="종가(현재가)")
    volume = Column(BigInteger, comment="거래량")
    trading_value = Column(BigInteger, comment="거래대금")
    
    # 변동 정보
    change_amount = Column(Numeric(12,2), comment="전일대비 변동금액")
    price_change_percent = Column(Numeric(10,4), comment="전일대비 등락율(%)")
    volume_change = Column(BigInteger, comment="전일대비 거래량 변화")
    volume_change_percent = Column(Numeric(10,4), comment="전일대비 거래량 증감율(%)")
    
    # 기준가 정보
    previous_close_price = Column(Numeric(12,2), comment="전일종가")
    
    # 수정주가 관련 정보
    adjusted_price_type = Column(String(20), comment="수정주가구분")
    adjustment_ratio = Column(Numeric(10,6), comment="수정비율")
    adjusted_price_event = Column(String(100), comment="수정주가이벤트")
    
    # 업종 분류
    major_industry_type = Column(String(20), comment="대업종구분")
    minor_industry_type = Column(String(20), comment="소업종구분")
    
    # 추가 정보
    stock_info = Column(String(100), comment="종목정보")
    
    created_at = Column(TIMESTAMP(timezone=True), default=datetime.utcnow, comment="생성시간")
    
    __table_args__ = (
        Index('idx_stock_prices_symbol_time', 'symbol', 'time', 'interval_type'),
        Index('idx_stock_prices_time_desc', 'time', postgresql_using='btree', postgresql_ops={'time': 'DESC'}),
        Index('idx_stock_prices_symbol_interval', 'symbol', 'interval_type'),
        Index('idx_stock_prices_date_symbol', 'time', 'symbol'),  # 일자별 조회용 인덱스
        {'comment': '주가 데이터 - 키움 API 주식일봉차트조회 (TimescaleDB 하이퍼테이블)'}
    )


class SupplyDemand(TimescaleBase):
    """수급 데이터 (키움 API ka10059 - 종목별투자자기관별)"""
    __tablename__ = "supply_demand"
    
    date = Column(TIMESTAMP(timezone=True), primary_key=True, nullable=False, comment="날짜")
    symbol = Column(String(10), primary_key=True, nullable=False, comment="종목코드")
    
    # 현재가 정보
    current_price = Column(Numeric(12,2), comment="현재가")
    price_change_sign = Column(String(5), comment="대비기호")
    price_change = Column(Numeric(12,2), comment="전일대비")
    price_change_percent = Column(Numeric(10,4), comment="등락율(%)")
    
    # 거래 정보
    accumulated_volume = Column(BigInteger, comment="누적거래량")
    accumulated_value = Column(BigInteger, comment="누적거래대금")
    
    # 투자자별 수급 데이터 (단위: 원 또는 주)
    individual_investor = Column(BigInteger, comment="개인투자자")
    foreign_investor = Column(BigInteger, comment="외국인투자자")
    institution_total = Column(BigInteger, comment="기관계")
    
    # 기관 세부 분류
    financial_investment = Column(BigInteger, comment="금융투자")
    insurance = Column(BigInteger, comment="보험")
    investment_trust = Column(BigInteger, comment="투신")
    other_financial = Column(BigInteger, comment="기타금융")
    bank = Column(BigInteger, comment="은행")
    pension_fund = Column(BigInteger, comment="연기금등")
    private_fund = Column(BigInteger, comment="사모펀드")
    
    # 기타 분류
    government = Column(BigInteger, comment="국가")
    other_corporation = Column(BigInteger, comment="기타법인")
    domestic_foreign = Column(BigInteger, comment="내외국인")
    
    created_at = Column(TIMESTAMP(timezone=True), default=datetime.utcnow, comment="생성시간")
    
    __table_args__ = (
        Index('idx_supply_demand_date_symbol', 'date', 'symbol'),
        Index('idx_supply_demand_symbol_date', 'symbol', 'date'),
        {'comment': '수급 데이터 - 키움 API 종목별투자자기관별 (TimescaleDB 하이퍼테이블)'}
    )


class MarketIndex(TimescaleBase):
    """시장 지수 데이터 (코스피, 코스닥 등)"""
    __tablename__ = "market_indices"
    
    time = Column(TIMESTAMP(timezone=True), primary_key=True, nullable=False, comment="시간 (UTC)")
    index_code = Column(String(20), primary_key=True, nullable=False, comment="지수 코드 (KOSPI, KOSDAQ)")
    
    # 지수 정보
    index_value = Column(Numeric(12,2), nullable=False, comment="지수 값")
    change_amount = Column(Numeric(12,2), comment="전일대비 변동")
    price_change_percent = Column(Numeric(10,4), comment="전일대비 변동률(%)")
    
    # 거래 정보
    volume = Column(BigInteger, comment="거래량")
    trading_value = Column(BigInteger, comment="거래대금")
    
    # 시장 정보
    rise_count = Column(Integer, comment="상승 종목 수")
    fall_count = Column(Integer, comment="하락 종목 수")
    unchanged_count = Column(Integer, comment="보합 종목 수")
    
    created_at = Column(TIMESTAMP(timezone=True), default=datetime.utcnow, comment="생성시간")
    
    __table_args__ = (
        Index('idx_market_indices_index_time', 'index_code', 'time'),
        Index('idx_market_indices_time_desc', 'time', postgresql_using='btree', postgresql_ops={'time': 'DESC'}),
        {'comment': '시장 지수 데이터 (TimescaleDB 하이퍼테이블)'}
    )

