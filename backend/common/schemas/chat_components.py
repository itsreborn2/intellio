"""
구조화된 채팅 메시지 컴포넌트 스키마 정의.

이 모듈은 채팅 메시지를 다양한 컴포넌트(제목, 단락, 차트, 이미지 등)로 구조화하는 
Pydantic 모델들을 정의합니다.
"""
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Literal, Union, Optional
from datetime import datetime


# --- 복합 컴포넌트 ---
class BarChartData(BaseModel):
    """막대 차트 데이터 모델"""
    labels: List[str] = Field(..., description="X축 라벨 목록")
    datasets: List[Dict[str, Any]] = Field(..., description="데이터셋 목록 (예: [{'label': '매출', 'data': [100, 120]}, ...])")


class BarChartComponent(BaseModel):
    """막대 차트 컴포넌트 모델"""
    type: Literal['bar_chart'] = 'bar_chart'
    title: Optional[str] = Field(None, description="차트 제목")
    data: BarChartData = Field(..., description="차트 데이터")


class LineChartData(BaseModel):
    """선 차트 데이터 모델"""
    labels: List[str] = Field(..., description="X축 라벨 목록")
    datasets: List[Dict[str, Any]] = Field(..., description="데이터셋 목록 (예: [{'label': '주가', 'data': [50000, 52000]}])")


class LineChartComponent(BaseModel):
    """선 차트 컴포넌트 모델"""
    type: Literal['line_chart'] = 'line_chart'
    title: Optional[str] = Field(None, description="차트 제목")
    data: LineChartData = Field(..., description="차트 데이터")


class MixedChartData(BaseModel):
    """혼합 차트 데이터 모델"""
    labels: List[str] = Field(..., description="X축 라벨 목록")
    bar_datasets: List[Dict[str, Any]] = Field(..., description="막대 차트 데이터셋 목록 (왼쪽 Y축)")
    line_datasets: List[Dict[str, Any]] = Field(..., description="선 차트 데이터셋 목록 (오른쪽 Y축)")
    y_axis_left_title: Optional[str] = Field(None, description="왼쪽 Y축 제목")
    y_axis_right_title: Optional[str] = Field(None, description="오른쪽 Y축 제목")


class MixedChartComponent(BaseModel):
    """혼합 차트 컴포넌트 모델 (막대 + 선 차트)"""
    type: Literal['mixed_chart'] = 'mixed_chart'
    title: Optional[str] = Field(None, description="차트 제목")
    data: MixedChartData = Field(..., description="차트 데이터")


class PriceChartData(BaseModel):
    """주가차트 데이터 모델"""
    symbol: str = Field(..., description="종목코드")
    name: str = Field(..., description="종목명")
    candle_data: List[Dict[str, Any]] = Field(..., description="캔들스틱 데이터 (OHLCV)")
    volume_data: Optional[List[Dict[str, Any]]] = Field(None, description="거래량 데이터")
    moving_averages: Optional[List[Dict[str, Any]]] = Field(None, description="이동평균선 데이터")
    support_lines: Optional[List[Dict[str, Any]]] = Field(None, description="지지선 데이터")
    resistance_lines: Optional[List[Dict[str, Any]]] = Field(None, description="저항선 데이터")
    period: Optional[str] = Field(None, description="조회 기간")
    interval: Optional[str] = Field(None, description="차트 간격")
    metadata: Optional[Dict[str, Any]] = Field(None, description="추가 메타데이터")


class PriceChartComponent(BaseModel):
    """주가차트 컴포넌트 모델"""
    type: Literal['price_chart'] = 'price_chart'
    title: Optional[str] = Field(None, description="차트 제목")
    data: PriceChartData = Field(..., description="주가차트 데이터")


class TechnicalIndicatorData(BaseModel):
    """기술적 지표 데이터 모델 (시계열 데이터)"""
    name: str = Field(..., description="지표명")
    data: List[float] = Field(..., description="지표 값 배열")
    color: Optional[str] = Field(None, description="지표 색상")
    chart_type: Literal['line', 'bar', 'area'] = Field(default='line', description="차트 타입")
    y_axis_id: Optional[str] = Field(default='primary', description="Y축 ID (primary, secondary)")
    line_style: Literal['solid', 'dashed', 'dotted'] = Field(default='solid', description="선 스타일")


class TechnicalIndicatorChartData(BaseModel):
    """기술적 지표 차트 데이터 모델"""
    symbol: str = Field(..., description="종목코드")
    name: str = Field(..., description="종목명")
    dates: List[str] = Field(..., description="날짜 배열 (X축)")
    candle_data: Optional[List[Dict[str, Any]]] = Field(None, description="주가 캔들 데이터 (선택적)")
    indicators: List[TechnicalIndicatorData] = Field(..., max_items=5, description="기술적 지표 목록 (최대 5개)")
    y_axis_configs: Optional[Dict[str, Dict[str, Any]]] = Field(None, description="Y축 설정")
    period: Optional[str] = Field(None, description="조회 기간")
    metadata: Optional[Dict[str, Any]] = Field(None, description="추가 메타데이터")


class TechnicalIndicatorChartComponent(BaseModel):
    """기술적 지표 차트 컴포넌트 모델"""
    type: Literal['technical_indicator_chart'] = 'technical_indicator_chart'
    title: Optional[str] = Field(None, description="차트 제목")
    data: TechnicalIndicatorChartData = Field(..., description="기술적 지표 차트 데이터")


class ImageComponent(BaseModel):
    """이미지 컴포넌트 모델"""
    type: Literal['image'] = 'image'
    url: str = Field(..., description="이미지 URL")
    alt: Optional[str] = Field(None, description="대체 텍스트")
    caption: Optional[str] = Field(None, description="이미지 캡션 또는 설명")


class TableHeader(BaseModel):
    """테이블 헤더 모델"""
    key: str = Field(..., description="데이터 매핑용 키")
    label: str = Field(..., description="표시될 헤더 이름")


class TableData(BaseModel):
    """테이블 데이터 모델"""
    headers: List[TableHeader] = Field(..., description="테이블 헤더 목록")
    rows: List[Dict[str, Any]] = Field(..., description="각 행은 {header.key: value} 형태의 딕셔너리")


class TableComponent(BaseModel):
    """테이블 컴포넌트 모델"""
    type: Literal['table'] = 'table'
    title: Optional[str] = Field(None, description="테이블 제목")
    data: TableData = Field(..., description="테이블 데이터")


# --- 세분화된 텍스트 컴포넌트 ---
class HeadingComponent(BaseModel):
    """제목 컴포넌트 모델"""
    type: Literal['heading'] = 'heading'
    level: int = Field(..., ge=1, le=6, description="제목 레벨 (1-6)")
    content: str = Field(..., description="제목 텍스트")


class ParagraphComponent(BaseModel):
    """단락 컴포넌트 모델"""
    type: Literal['paragraph'] = 'paragraph'
    content: str = Field(..., description="단락 텍스트 (인라인 서식은 Markdown 미지원)")


class ListItemComponent(BaseModel):
    """목록 항목 모델"""
    content: str = Field(..., description="목록 항목 텍스트")
    # sub_items: Optional[List['ListItemComponent']] = None # 추후 중첩 리스트 지원 시


class ListComponent(BaseModel):
    """목록 컴포넌트 모델"""
    type: Literal['list'] = 'list'
    ordered: bool = Field(default=False, description="순서 있는 목록 여부 (True: <ol>, False: <ul>)")
    items: List[ListItemComponent] = Field(..., description="목록 항목들")


class CodeBlockComponent(BaseModel):
    """코드 블록 컴포넌트 모델"""
    type: Literal['code_block'] = 'code_block'
    language: Optional[str] = Field(None, description="코드 언어 (syntax highlighting용)")
    content: str = Field(..., description="코드 내용")


# --- 모든 컴포넌트 타입의 Union ---
MessageComponent = Union[
    HeadingComponent,
    ParagraphComponent,
    ListComponent,
    CodeBlockComponent,
    BarChartComponent,
    LineChartComponent,
    MixedChartComponent,
    PriceChartComponent,
    TechnicalIndicatorChartComponent,
    ImageComponent,
    TableComponent,
    # 필요시 추가 컴포넌트 정의
]


# --- SSE 'complete' 이벤트로 전송될 최종 구조 ---
class StructuredChatResponse(BaseModel):
    """구조화된 채팅 응답 모델"""
    message_id: str = Field(..., description="해당 메시지의 DB ID")
    content: str = Field(..., description="AI 답변 텍스트")
    components: List[MessageComponent] = Field(..., description="AI 답변을 구성하는 컴포넌트 리스트")
    metadata: Optional[Dict[str, Any]] = Field(None, description="메타데이터 (처리 시간 등)")
    timestamp: float = Field(..., description="타임스탬프 (Unix 시간, 초)")
    elapsed: float = Field(..., description="처리 시간 (초)") 