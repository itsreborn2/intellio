"""
PDF 생성 서비스

이 모듈은 채팅 세션의 메시지를 PDF로 변환하는 기능을 제공합니다.
"""

import asyncio
import io
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import mplfinance as mpf
import numpy as np
import pandas as pd
from loguru import logger
from markdown_it import MarkdownIt
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from common.core.config import settings


# markdown-it-py를 사용하여 마크다운을 HTML로 변환하는 함수
def convert_markdown_to_html(text: str) -> str:
    """
    마크다운 텍스트를 HTML로 변환합니다.

    Args:
        text: 마크다운 형식의 텍스트

    Returns:
        HTML로 변환된 텍스트
    """
    if not text:
        return ""

    # 기본 마크다운 변환기 사용
    md = MarkdownIt()

    # 필요한 확장 기능 활성화
    md.enable("table")  # 테이블 지원 활성화

    # 마크다운을 HTML로 변환
    html = md.render(text)

    # 변환된 HTML을 로그로 출력(디버깅용)
    # print("==== 변환된 HTML ====")
    # print(html)

    # <strong> 태그가 ReportLab에서 잘 작동하도록 <b> 태그로 변환
    html = html.replace("<strong>", "<b>").replace("</strong>", "</b>")

    return html


# HTML을 ReportLab 형식으로 변환하는 함수
def convert_html_to_reportlab(html_content: str) -> List[Dict[str, Any]]:
    """
    HTML 텍스트를 ReportLab 형식의 요소로 변환합니다.

    Args:
        html_content: HTML 형식의 텍스트

    Returns:
        스타일 정보가 포함된 단락 목록
    """
    if not html_content:
        return []

    result = []

    # HTML 내용을 줄 단위로 처리
    lines = html_content.split("\n")
    current_block = []
    current_style = "Normal-KO"

    for line in lines:
        # 빈 줄 건너뛰기
        if not line.strip():
            if current_block:
                result.append({"text": "".join(current_block), "style": current_style})
                current_block = []
                current_style = "Normal-KO"
            continue

        # 헤더 태그 확인
        if re.search(r"<h([1-6])[^>]*>(.*?)</h\1>", line):
            # 이전 블록이 있으면 추가
            if current_block:
                result.append({"text": "".join(current_block), "style": current_style})
                current_block = []

            # 헤더 수준 추출
            header_match = re.search(r"<h([1-6])[^>]*>(.*?)</h\1>", line)
            if header_match:
                level = header_match.group(1)
                content = header_match.group(2)
                result.append({"text": content, "style": f"Heading{level}-KO"})
            continue

        # 목록 항목 확인
        if "<li>" in line:
            # <li> 태그를 추출하여 처리
            li_content = re.sub(r"<li[^>]*>(.*?)</li>", r"• \1", line)
            current_block.append(li_content)
            current_style = "ListItem-KO"
            continue

        # 코드 블록 확인
        if "<pre>" in line or "<code>" in line:
            # 이전 블록이 있으면 추가
            if current_block:
                result.append({"text": "".join(current_block), "style": current_style})
                current_block = []

            # 코드 컨텐츠 추출
            code_content = re.sub(r"<pre[^>]*><code[^>]*>(.*?)</code></pre>", r"\1", line)
            code_content = re.sub(r"<code[^>]*>(.*?)</code>", r"\1", code_content)

            result.append({"text": code_content, "style": "Code-KO"})
            continue

        # 인용구 확인
        if "<blockquote>" in line:
            quote_content = re.sub(r"<blockquote[^>]*>(.*?)</blockquote>", r"\1", line)
            current_block.append(quote_content)
            current_style = "Quote-KO"
            continue

        # 일반 텍스트 (다른 특별한 태그가 없는 경우)
        current_block.append(line)

    # 마지막 블록 처리
    if current_block:
        result.append({"text": "".join(current_block), "style": current_style})

    return result


# 테이블 추출 및 변환 함수 추가
def extract_tables_from_html(html_content: str) -> List[Dict[str, Any]]:
    """
    HTML 콘텐츠에서 테이블을 추출하고 ReportLab 테이블 데이터로 변환합니다.

    Args:
        html_content: HTML 형식의 텍스트

    Returns:
        ReportLab 테이블 정보 목록
    """
    tables = []

    # 정규식으로 테이블 태그 추출
    table_pattern = re.compile(r"<table>(.*?)</table>", re.DOTALL)
    table_matches = table_pattern.findall(html_content)

    for table_html in table_matches:
        # 행 추출
        rows = []
        row_pattern = re.compile(r"<tr>(.*?)</tr>", re.DOTALL)
        row_matches = row_pattern.findall(table_html)

        for row_html in row_matches:
            # 헤더 셀 추출
            cell_pattern = re.compile(r"<t[hd]>(.*?)</t[hd]>", re.DOTALL)
            cell_matches = cell_pattern.findall(row_html)

            # 각 셀의 HTML 태그 제거
            row = []
            for cell_html in cell_matches:
                # HTML 태그 제거
                cell_text = re.sub(r"<[^>]+>", "", cell_html).strip()
                row.append(cell_text)

            if row:  # 비어있지 않은 행만 추가
                rows.append(row)

        if rows:  # 비어있지 않은 테이블만 추가
            tables.append({"data": rows, "type": "table"})

    return tables


# convert_markdown 함수를 확장해 테이블 지원 추가
def convert_markdown(text: str) -> List[Dict[str, Any]]:
    """
    마크다운 텍스트를 HTML로 변환하여 ReportLab이 처리할 수 있는 형식으로 반환합니다.

    Args:
        text: 마크다운 형식의 텍스트

    Returns:
        HTML 형식의 단락 목록과 테이블 목록
    """
    if not text:
        return []

    try:
        # 마크다운을 HTML로 변환
        html = convert_markdown_to_html(text)

        # 테이블 추출 (테이블 태그 포함된 부분)
        tables = extract_tables_from_html(html)

        # 테이블을 제외한 HTML 처리 (테이블 태그를 임시 마커로 대체)
        table_placeholders = {}
        for i, table in enumerate(tables):
            placeholder = f"__TABLE_PLACEHOLDER_{i}__"
            table_html = re.search(r"(<table>.*?</table>)", html, re.DOTALL)
            if table_html:
                html = html.replace(table_html.group(1), placeholder, 1)
                table_placeholders[placeholder] = table

        # HTML을 단락으로 분리해 ReportLab 형식으로 변환
        result = []

        # 단락 분리를 위해 p 태그로 구분
        paragraphs = re.split(r"(<\/?(?:p|h[1-6]|ul|ol|li|pre|blockquote)[^>]*>)", html)
        buffer = []
        current_style = "Paragraph-KO"  # 기본적으로 들여쓰기가 적용된 단락 스타일 사용

        for part in paragraphs:
            if not part.strip():
                continue

            # 테이블 플레이스홀더 확인
            table_match = None
            for placeholder in table_placeholders:
                if placeholder in part:
                    # 이전 내용이 있으면 먼저 처리
                    if buffer:
                        result.append({"text": "".join(buffer), "style": current_style})
                        buffer = []

                    # 테이블 데이터 추가
                    result.append(table_placeholders[placeholder])

                    # 플레이스홀더를 제거한 나머지 부분 처리
                    remaining = part.replace(placeholder, "")
                    if remaining.strip():
                        buffer.append(remaining)

                    table_match = True
                    break

            if table_match:
                continue

            # HTML 태그 처리
            if part.startswith("<h"):
                # 헤딩 태그 처리
                if buffer:
                    result.append({"text": "".join(buffer), "style": current_style})
                    buffer = []

                level = int(part[2]) if len(part) > 2 and part[2].isdigit() else 1

                # 최상위 헤딩(레벨 1)인 경우 앞에 더 명확한 구분을 위한 여백 추가 (첫 번째 헤딩이 아닌 경우에만)
                if level == 1 and result:
                    result.append({"text": "", "style": "Normal-KO"})  # 첫 번째 빈 줄
                    result.append({"text": "", "style": "Normal-KO"})  # 두 번째 빈 줄
                    result.append({"text": "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", "style": "Normal-KO"})  # 구분선
                    result.append({"text": "", "style": "Normal-KO"})  # 세 번째 빈 줄

                current_style = f"Heading{min(level, 6)}-KO"

            elif part.startswith("</h"):
                # 헤딩 끝
                if buffer:
                    result.append({"text": "".join(buffer), "style": current_style})
                    buffer = []
                current_style = "Paragraph-KO"  # 헤딩 후에도 들여쓰기가 적용된 단락 스타일로 복귀

            elif part.startswith("<p"):
                # 새 단락 시작
                if buffer and "".join(buffer).strip():
                    result.append({"text": "".join(buffer), "style": current_style})
                    buffer = []
                current_style = "Paragraph-KO"  # 들여쓰기가 적용된 단락 스타일 사용

            elif part.startswith("</p>"):
                # 단락 끝
                if buffer:
                    result.append({"text": "".join(buffer), "style": current_style})
                    buffer = []

            elif part.startswith("<ul") or part.startswith("<ol"):
                # 리스트 시작
                if buffer:
                    result.append({"text": "".join(buffer), "style": current_style})
                    buffer = []

            elif part.startswith("</ul>") or part.startswith("</ol>"):
                # 리스트 끝
                if buffer:
                    result.append({"text": "".join(buffer), "style": current_style})
                    buffer = []

            elif part.startswith("<li"):
                # 리스트 항목 시작
                if buffer:
                    result.append({"text": "".join(buffer), "style": current_style})
                    buffer = []
                buffer.append("• ")

            elif part.startswith("</li>"):
                # 리스트 항목 끝
                if buffer:
                    result.append({"text": "".join(buffer), "style": current_style})
                    buffer = []

            elif part.startswith("<pre") or part.startswith("<blockquote"):
                # 블록 요소 시작
                if buffer:
                    result.append({"text": "".join(buffer), "style": current_style})
                    buffer = []
                current_style = "Code-KO" if part.startswith("<pre") else "Normal-KO"

            elif part.startswith("</pre>") or part.startswith("</blockquote>"):
                # 블록 요소 끝
                if buffer:
                    result.append({"text": "".join(buffer), "style": current_style})
                    buffer = []
                current_style = "Paragraph-KO"  # 블록 요소 후에도 들여쓰기가 적용된 단락 스타일로 복귀

            else:
                # 일반 텍스트 또는 인라인 HTML
                buffer.append(part)

        # 남은 내용 처리
        if buffer:
            result.append({"text": "".join(buffer), "style": current_style})

        return result

    except Exception as e:
        logger.error(f"마크다운 변환 중 오류 발생: {str(e)}")
        # 오류 발생 시 원본 텍스트를 단순 단락으로 반환
        return [{"text": text, "style": "Normal-KO"}]


def replace_chart_placeholders_with_components(content: str, components: Optional[List[Dict[str, Any]]]) -> str:
    """
    content의 차트 placeholder를 components의 실제 차트 데이터로 대체합니다.

    Args:
        content: 마크다운 텍스트 (placeholder 포함)
        components: 구조화된 컴포넌트 배열

    Returns:
        placeholder가 차트 설명으로 대체된 텍스트
    """
    if not content or not components:
        return content

    # 차트 placeholder 패턴들
    chart_placeholders = {
        "[CHART_PLACEHOLDER:PRICE_CHART]": "price_chart",
        "[CHART_PLACEHOLDER:TECHNICAL_INDICATOR_CHART]": "technical_indicator_chart",
        "[CHART_PLACEHOLDER:TREND_FOLLOWING_CHART]": "technical_indicator_chart",
        "[CHART_PLACEHOLDER:MOMENTUM_CHART]": "technical_indicator_chart",
    }

    result_content = content

    # 각 placeholder를 찾아서 대체
    for placeholder, chart_type in chart_placeholders.items():
        if placeholder in result_content:
            # 해당 타입의 차트 컴포넌트 찾기
            chart_component = None
            for component in components:
                if component.get("type") == chart_type:
                    chart_component = component
                    break

            if chart_component:
                # 차트 데이터를 텍스트로 변환
                chart_text = convert_chart_component_to_text(chart_component)
                result_content = result_content.replace(placeholder, chart_text)
            else:
                # 차트 컴포넌트가 없으면 placeholder 제거
                result_content = result_content.replace(placeholder, "")

    return result_content


def convert_chart_component_to_text(chart_component: Dict[str, Any]) -> str:
    """
    차트 컴포넌트를 PDF에 표시할 수 있는 텍스트로 변환합니다.

    Args:
        chart_component: 차트 컴포넌트 데이터

    Returns:
        차트 정보를 설명하는 텍스트
    """
    chart_type = chart_component.get("type", "")
    chart_data = chart_component.get("data", {})
    title = chart_component.get("title", "차트")

    if chart_type == "price_chart":
        return convert_price_chart_to_text(chart_data, title)
    elif chart_type == "technical_indicator_chart":
        return convert_technical_indicator_chart_to_text(chart_data, title)
    elif chart_type == "bar_chart":
        return convert_bar_chart_to_text(chart_data, title)
    elif chart_type == "line_chart":
        return convert_line_chart_to_text(chart_data, title)
    elif chart_type == "mixed_chart":
        return convert_mixed_chart_to_text(chart_data, title)
    else:
        return f"\n**{title}**\n차트 데이터가 포함되어 있습니다.\n"


def convert_price_chart_to_text(chart_data: Dict[str, Any], title: str) -> str:
    """주가 차트 데이터를 텍스트로 변환"""
    try:
        text_parts = [f"\n**{title}**\n"]

        symbol = chart_data.get("symbol", "")
        name = chart_data.get("name", "")
        candle_data = chart_data.get("candle_data", [])

        if symbol and name:
            text_parts.append(f"종목: {name} ({symbol})\n")

        if candle_data and len(candle_data) > 0:
            # 최근 데이터 몇 개만 표시
            recent_data = candle_data[-5:] if len(candle_data) >= 5 else candle_data
            text_parts.append("\n**최근 주가 동향:**\n")

            for data in recent_data:
                date = data.get("time", "")
                close = data.get("close", 0)
                volume = data.get("volume", 0)
                change = data.get("price_change_percent", 0)

                if date and close:
                    change_str = f"({change:+.2f}%)" if change != 0 else ""
                    volume_str = f", 거래량: {volume:,}" if volume > 0 else ""
                    text_parts.append(f"- {date}: {close:,}원 {change_str}{volume_str}\n")

        # 이동평균선 정보
        moving_averages = chart_data.get("moving_averages", [])
        if moving_averages:
            text_parts.append("\n**이동평균선:**\n")
            for ma in moving_averages[:3]:  # 최대 3개만 표시
                period = ma.get("period", "")
                current_value = ma.get("current_value", 0)
                if period and current_value:
                    text_parts.append(f"- {period}일선: {current_value:,}원\n")

        # 지지선/저항선 정보
        support_lines = chart_data.get("support_lines", [])
        resistance_lines = chart_data.get("resistance_lines", [])

        if support_lines:
            support_prices = [f"{line.get('price', 0):,}원" for line in support_lines[:3]]
            text_parts.append(f"\n**주요 지지선:** {', '.join(support_prices)}\n")

        if resistance_lines:
            resistance_prices = [f"{line.get('price', 0):,}원" for line in resistance_lines[:3]]
            text_parts.append(f"**주요 저항선:** {', '.join(resistance_prices)}\n")

        return "".join(text_parts)
    except Exception as e:
        logger.error(f"주가차트 텍스트 변환 오류: {str(e)}")
        return f"\n**{title}**\n주가 차트 데이터가 포함되어 있습니다.\n"


def convert_technical_indicator_chart_to_text(chart_data: Dict[str, Any], title: str) -> str:
    """기술적 지표 차트 데이터를 텍스트로 변환"""
    try:
        text_parts = [f"\n**{title}**\n"]

        symbol = chart_data.get("symbol", "")
        name = chart_data.get("name", "")
        indicators = chart_data.get("indicators", [])

        if symbol and name:
            text_parts.append(f"종목: {name} ({symbol})\n")

        if indicators:
            text_parts.append("\n**기술적 지표 현재 값:**\n")

            for indicator in indicators:
                indicator_name = indicator.get("name", "")
                data = indicator.get("data", [])

                if indicator_name and data and len(data) > 0:
                    # 최신 값 가져오기
                    latest_value = data[-1] if isinstance(data[-1], (int, float)) else None
                    if latest_value is not None:
                        text_parts.append(f"- {indicator_name}: {latest_value:.2f}\n")

        return "".join(text_parts)
    except Exception as e:
        logger.error(f"기술적지표차트 텍스트 변환 오류: {str(e)}")
        return f"\n**{title}**\n기술적 지표 차트 데이터가 포함되어 있습니다.\n"


def convert_bar_chart_to_text(chart_data: Dict[str, Any], title: str) -> str:
    """바 차트 데이터를 텍스트로 변환"""
    try:
        text_parts = [f"\n**{title}**\n"]

        labels = chart_data.get("labels", [])
        datasets = chart_data.get("datasets", [])

        if labels and datasets:
            # 테이블 형태로 변환
            text_parts.append("\n")

            # 헤더 구성
            header = "| 구분 |"
            for dataset in datasets:
                dataset_label = dataset.get("label", "데이터")
                header += f" {dataset_label} |"
            text_parts.append(header + "\n")

            # 구분선
            separator = "|---|"
            for _ in datasets:
                separator += "---|"
            text_parts.append(separator + "\n")

            # 데이터 행
            for i, label in enumerate(labels):
                row = f"| {label} |"
                for dataset in datasets:
                    data = dataset.get("data", [])
                    value = data[i] if i < len(data) else 0
                    if isinstance(value, float):
                        row += f" {value:.2f} |"
                    else:
                        row += f" {value:,} |"
                text_parts.append(row + "\n")

        return "".join(text_parts)
    except Exception as e:
        logger.error(f"바차트 텍스트 변환 오류: {str(e)}")
        return f"\n**{title}**\n바 차트 데이터가 포함되어 있습니다.\n"


def convert_line_chart_to_text(chart_data: Dict[str, Any], title: str) -> str:
    """라인 차트 데이터를 텍스트로 변환"""
    try:
        text_parts = [f"\n**{title}**\n"]

        labels = chart_data.get("labels", [])
        datasets = chart_data.get("datasets", [])

        if labels and datasets:
            # 각 데이터셋별로 최신 값과 추세 표시
            for dataset in datasets:
                dataset_label = dataset.get("label", "데이터")
                data = dataset.get("data", [])

                if data and len(data) >= 2:
                    latest_value = data[-1]
                    previous_value = data[-2]
                    change = latest_value - previous_value
                    change_pct = (change / previous_value * 100) if previous_value != 0 else 0

                    change_str = f"({change:+.2f}, {change_pct:+.1f}%)" if change != 0 else ""
                    text_parts.append(f"- {dataset_label}: {latest_value:.2f} {change_str}\n")

        return "".join(text_parts)
    except Exception as e:
        logger.error(f"라인차트 텍스트 변환 오류: {str(e)}")
        return f"\n**{title}**\n라인 차트 데이터가 포함되어 있습니다.\n"


def convert_mixed_chart_to_text(chart_data: Dict[str, Any], title: str) -> str:
    """혼합 차트 데이터를 텍스트로 변환"""
    try:
        text_parts = [f"\n**{title}**\n"]

        labels = chart_data.get("labels", [])
        bar_datasets = chart_data.get("bar_datasets", [])
        line_datasets = chart_data.get("line_datasets", [])

        if labels and (bar_datasets or line_datasets):
            # 테이블 형태로 변환
            text_parts.append("\n")

            # 헤더 구성
            header = "| 구분 |"
            all_datasets = bar_datasets + line_datasets
            for dataset in all_datasets:
                dataset_label = dataset.get("label", "데이터")
                header += f" {dataset_label} |"
            text_parts.append(header + "\n")

            # 구분선
            separator = "|---|"
            for _ in all_datasets:
                separator += "---|"
            text_parts.append(separator + "\n")

            # 데이터 행
            for i, label in enumerate(labels):
                row = f"| {label} |"
                for dataset in all_datasets:
                    data = dataset.get("data", [])
                    value = data[i] if i < len(data) else 0
                    if isinstance(value, float):
                        row += f" {value:.2f} |"
                    else:
                        row += f" {value:,} |"
                text_parts.append(row + "\n")

        return "".join(text_parts)
    except Exception as e:
        logger.error(f"혼합차트 텍스트 변환 오류: {str(e)}")
        return f"\n**{title}**\n혼합 차트 데이터가 포함되어 있습니다.\n"


class PDFService:
    """PDF 생성 서비스 클래스"""

    def __init__(self):
        """초기화"""
        # 폰트 등록 - 나눔고딕 폰트를 사용
        font_path = Path(__file__).parent.parent.parent / "resource" / "fonts"

        # 폰트 디렉토리 확인
        try:
            # 기본 등록된 폰트 확인
            registered_fonts = pdfmetrics.getRegisteredFontNames()

            if "NanumGothic" not in registered_fonts:
                # 폰트 디렉토리가 없거나 파일이 없으면 기본 폰트 사용
                if not font_path.exists():
                    logger.warning(f"폰트 디렉토리({font_path})가 없습니다. 기본 폰트를 사용합니다.")
                else:
                    # 나눔고딕 폰트 등록
                    nanum_regular_path = font_path / "NanumGothic.ttf"
                    nanum_bold_path = font_path / "NanumGothicBold.ttf"

                    if not nanum_regular_path.exists() or not nanum_bold_path.exists():
                        logger.warning(f"나눔고딕 폰트 파일({nanum_regular_path}, {nanum_bold_path})이 없습니다. 기본 폰트를 사용합니다.")
                    else:
                        pdfmetrics.registerFont(TTFont("NanumGothic", str(nanum_regular_path)))
                        pdfmetrics.registerFont(TTFont("NanumGothicBold", str(nanum_bold_path)))
                        logger.info("나눔고딕 폰트 등록 완료")
        except Exception as e:
            logger.warning(f"폰트 등록 중 오류 발생: {str(e)}")

        # matplotlib 한글 폰트 설정
        self._setup_matplotlib_font(font_path)

    def _setup_matplotlib_font(self, font_path: Path):
        """matplotlib에서 한글 폰트를 사용할 수 있도록 설정합니다."""
        try:
            # 나눔고딕 폰트 경로
            nanum_font_path = font_path / "NanumGothic.ttf"

            if nanum_font_path.exists():
                # matplotlib에 폰트 등록
                fm.fontManager.addfont(str(nanum_font_path))
                plt.rcParams["font.family"] = "NanumGothic"
                plt.rcParams["axes.unicode_minus"] = False  # 마이너스 부호 깨짐 방지
                logger.info("matplotlib 한글 폰트 설정 완료")
            else:
                # 시스템 기본 한글 폰트 사용 시도
                available_fonts = [font.name for font in fm.fontManager.ttflist]
                korean_fonts = ["Malgun Gothic", "AppleGothic", "Noto Sans CJK KR", "Arial Unicode MS"]

                for font_name in korean_fonts:
                    if font_name in available_fonts:
                        plt.rcParams["font.family"] = font_name
                        plt.rcParams["axes.unicode_minus"] = False
                        logger.info(f"matplotlib 한글 폰트 설정 완료: {font_name}")
                        break
                else:
                    logger.warning("matplotlib 한글 폰트를 찾을 수 없습니다. 기본 폰트를 사용합니다.")
                    plt.rcParams["font.family"] = "DejaVu Sans"
        except Exception as e:
            logger.warning(f"matplotlib 폰트 설정 중 오류 발생: {str(e)}")

    def _create_bar_chart_image(self, component: Dict[str, Any]) -> io.BytesIO:
        """바 차트 컴포넌트를 이미지로 변환하여 메모리 버퍼로 반환합니다."""
        try:
            data = component.get("data", {})
            title = component.get("title", "바 차트")
            labels = data.get("labels", [])
            datasets = data.get("datasets", [])

            if not labels or not datasets:
                return None

            # 한글 폰트 설정 (차트 생성 전에 먼저 설정)
            original_font_family = plt.rcParams.get("font.family", [])
            original_unicode_minus = plt.rcParams.get("axes.unicode_minus", True)

            try:
                # NanumGothic 폰트 시도
                font_path = Path(__file__).parent.parent.parent / "resource" / "fonts" / "NanumGothic.ttf"
                if font_path.exists():
                    # matplotlib 폰트 매니저에 등록
                    fm.fontManager.addfont(str(font_path))
                    plt.rcParams["font.family"] = "NanumGothic"
                    plt.rcParams["axes.unicode_minus"] = False
                else:
                    # 시스템 기본 한글 폰트 시도
                    available_fonts = [font.name for font in fm.fontManager.ttflist]
                    korean_fonts = ["Malgun Gothic", "AppleGothic", "Noto Sans CJK KR", "Arial Unicode MS"]

                    font_found = False
                    for font_name in korean_fonts:
                        if font_name in available_fonts:
                            plt.rcParams["font.family"] = font_name
                            plt.rcParams["axes.unicode_minus"] = False
                            font_found = True
                            break

                    if not font_found:
                        # 한글이 포함된 제목을 영문으로 대체
                        title = "Bar Chart"

            except Exception as font_error:
                logger.error(f"바차트 폰트 설정 실패: {font_error}")
                raise font_error

            fig, ax = plt.subplots(figsize=(10, 6))
            x = np.arange(len(labels))
            width = 0.8 / len(datasets)

            for i, dataset in enumerate(datasets):
                dataset_label = dataset.get("label", f"데이터 {i + 1}")
                dataset_data = dataset.get("data", [])
                color = dataset.get("backgroundColor", f"C{i}")
                bars = ax.bar(x + i * width, dataset_data, width, label=dataset_label, color=color, zorder=3)  # zorder를 높게 설정하여 축 선보다 앞에 표시
                for bar, value in zip(bars, dataset_data):
                    height = bar.get_height()
                    ax.text(
                        bar.get_x() + bar.get_width() / 2.0,
                        height,
                        f"{value:,.0f}" if isinstance(value, (int, float)) else str(value),
                        ha="center",
                        va="bottom",
                        fontsize=13,  # 폰트 크기 증가 (10 -> 13)
                        fontweight="bold",  # 텍스트를 굵게 표시
                    )

            ax.set_title(title, fontsize=18, fontweight="bold", pad=20)  # 제목 폰트 크기 증가 (16 -> 18)

            y_label_korean = "값"
            y_label_english = "Value"

            if len(datasets) == 1:
                y_label_korean = datasets[0].get("label", "값")
                y_label_english = datasets[0].get("label", "Value")

            ax.set_xlabel("")
            ax.set_ylabel(y_label_english if title == "Bar Chart" else y_label_korean, fontsize=14, fontweight="bold")  # Y축 레이블 폰트 크기 증가 (12 -> 14) 및 굵게

            ax.set_xticks(x + width * (len(datasets) - 1) / 2)
            ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=12, fontweight="bold")  # X축 레이블 굵게
            ax.tick_params(axis="both", which="major", labelsize=13)  # 눈금 레이블 크기 증가 (12 -> 13)
            if len(datasets) > 1:
                ax.legend(fontsize=13, frameon=True, fancybox=True, shadow=True)  # 범례 폰트 크기 증가 및 스타일 개선

            # 격자선을 뒤로 보내기 (zorder=1)
            ax.grid(True, alpha=0.3, axis="y", zorder=1)

            # 축 선을 뒤로 보내기 (zorder=2)
            for spine in ax.spines.values():
                spine.set_zorder(2)

            # x축 레이블이 날짜 형식인지 확인하고 포맷 적용
            try:
                # 첫 번째 레이블로 날짜 형식 확인
                if labels and ("-" in str(labels[0]) and len(str(labels[0])) >= 8):
                    # 날짜 형식으로 변환하여 x축 포맷 설정

                    import matplotlib.dates as mdates

                    # 레이블을 datetime 객체로 변환
                    date_labels = []
                    for label in labels:
                        try:
                            date_obj = pd.to_datetime(label)
                            date_labels.append(date_obj)
                        except:
                            break

                    if len(date_labels) == len(labels):  # 모든 레이블이 날짜 형식
                        ax.clear()  # 기존 플롯 클리어

                        # 날짜 x축으로 다시 그리기
                        x_positions = date_labels
                        for dataset in datasets:
                            label = dataset.get("label", "")
                            data_values = dataset.get("data", [])
                            color = dataset.get("backgroundColor", dataset.get("borderColor", "blue"))

                            ax.bar(x_positions, data_values, label=label, color=color, alpha=0.8, zorder=3)  # zorder 추가

                        ax.set_title(title, fontsize=18, fontweight="bold")  # 폰트 크기 증가
                        ax.set_xlabel("날짜", fontsize=14, fontweight="bold")  # 폰트 크기 증가
                        ax.set_ylabel("값", fontsize=14, fontweight="bold")  # 폰트 크기 증가
                        ax.legend(fontsize=13, frameon=True, fancybox=True, shadow=True)  # 폰트 크기 증가
                        ax.grid(True, alpha=0.3, axis="y", zorder=1)  # zorder 추가

                        # 날짜 포맷 설정
                        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
                        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha="right", fontsize=12, fontweight="bold")  # 폰트 크기 및 굵기 설정
                        ax.tick_params(axis="both", which="major", labelsize=13)  # Y축 눈금 레이블 크기 설정

                        # 축 선을 뒤로 보내기
                        for spine in ax.spines.values():
                            spine.set_zorder(2)
            except Exception as date_format_error:
                logger.debug(f"바차트 날짜 포맷 적용 실패: {date_format_error}")

            plt.tight_layout()

            buffer = io.BytesIO()
            plt.savefig(buffer, format="png", dpi=300, bbox_inches="tight", facecolor="white", edgecolor="none")
            buffer.seek(0)

            logger.debug(f"바 차트 이미지 메모리 버퍼 생성 완료, 크기: {len(buffer.getvalue())} bytes")
            return buffer
        except Exception as e:
            logger.error(f"바 차트 이미지 생성 오류: {str(e)}")
            return None
        finally:
            try:
                # 원래 폰트 설정 복원
                plt.rcParams["font.family"] = original_font_family
                plt.rcParams["axes.unicode_minus"] = original_unicode_minus
                plt.close("all")
            except Exception as cleanup_error:
                logger.error(f"바차트 matplotlib 리소스 정리 실패: {cleanup_error}")
                raise cleanup_error

    def _create_line_chart_image(self, component: Dict[str, Any]) -> io.BytesIO:
        """라인 차트 컴포넌트를 이미지로 변환하여 메모리 버퍼로 반환합니다."""
        try:
            data = component.get("data", {})
            title = component.get("title", "라인 차트")
            labels = data.get("labels", [])
            datasets = data.get("datasets", [])

            if not labels or not datasets:
                return None

            # 한글 폰트 설정 (차트 생성 전에 먼저 설정)
            original_font_family = plt.rcParams.get("font.family", [])
            original_unicode_minus = plt.rcParams.get("axes.unicode_minus", True)

            try:
                # NanumGothic 폰트 시도
                font_path = Path(__file__).parent.parent.parent / "resource" / "fonts" / "NanumGothic.ttf"
                if font_path.exists():
                    # matplotlib 폰트 매니저에 등록
                    fm.fontManager.addfont(str(font_path))
                    plt.rcParams["font.family"] = "NanumGothic"
                    plt.rcParams["axes.unicode_minus"] = False
                else:
                    # 시스템 기본 한글 폰트 시도
                    available_fonts = [font.name for font in fm.fontManager.ttflist]
                    korean_fonts = ["Malgun Gothic", "AppleGothic", "Noto Sans CJK KR", "Arial Unicode MS"]

                    font_found = False
                    for font_name in korean_fonts:
                        if font_name in available_fonts:
                            plt.rcParams["font.family"] = font_name
                            plt.rcParams["axes.unicode_minus"] = False
                            font_found = True
                            break

                    if not font_found:
                        # 한글이 포함된 제목을 영문으로 대체
                        title = "Line Chart"

            except Exception as font_error:
                logger.error(f"라인차트 폰트 설정 실패: {font_error}")
                raise font_error

            fig, ax = plt.subplots(figsize=(10, 6))

            for i, dataset in enumerate(datasets):
                dataset_label = dataset.get("label", f"데이터 {i + 1}")
                dataset_data = dataset.get("data", [])
                color = dataset.get("borderColor", f"C{i}")
                line_style = "--" if "borderDash" in dataset else "-"
                ax.plot(labels, dataset_data, label=dataset_label, color=color, linestyle=line_style, linewidth=2, marker="o", markersize=4)

            ax.set_title(title, fontsize=16, fontweight="bold", pad=20)
            ax.set_xlabel("", fontsize=12)
            ax.set_ylabel("Value" if title == "Line Chart" else "값", fontsize=12)
            plt.xticks(rotation=45, ha="right")
            ax.tick_params(axis="both", which="major", labelsize=12)
            if len(datasets) > 1:
                ax.legend(fontsize=12)
            ax.grid(True, alpha=0.3)

            # x축 레이블이 날짜 형식인지 확인하고 포맷 적용
            try:
                # 첫 번째 레이블로 날짜 형식 확인
                if labels and ("-" in str(labels[0]) and len(str(labels[0])) >= 8):
                    # 날짜 형식으로 변환하여 x축 포맷 설정

                    import matplotlib.dates as mdates

                    # 레이블을 datetime 객체로 변환
                    date_labels = []
                    for label in labels:
                        try:
                            date_obj = pd.to_datetime(label)
                            date_labels.append(date_obj)
                        except:
                            break

                    if len(date_labels) == len(labels):  # 모든 레이블이 날짜 형식
                        ax.clear()  # 기존 플롯 클리어

                        # 날짜 x축으로 다시 그리기
                        for i, dataset in enumerate(datasets):
                            dataset_label = dataset.get("label", f"데이터 {i + 1}")
                            dataset_data = dataset.get("data", [])
                            color = dataset.get("borderColor", f"C{i}")
                            line_style = "--" if "borderDash" in dataset else "-"
                            ax.plot(date_labels, dataset_data, label=dataset_label, color=color, linestyle=line_style, linewidth=2, marker="o", markersize=4)

                        ax.set_title(title, fontsize=16, fontweight="bold", pad=20)
                        ax.set_xlabel("", fontsize=12)
                        ax.set_ylabel("Value" if title == "Line Chart" else "값", fontsize=12)
                        if len(datasets) > 1:
                            ax.legend(fontsize=12)
                        ax.grid(True, alpha=0.3)
                        ax.tick_params(axis="both", which="major", labelsize=12)

                        # 날짜 포맷 설정
                        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
                        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha="right")
            except Exception as date_format_error:
                logger.debug(f"라인차트 날짜 포맷 적용 실패: {date_format_error}")

            plt.tight_layout()

            buffer = io.BytesIO()
            plt.savefig(buffer, format="png", dpi=300, bbox_inches="tight", facecolor="white", edgecolor="none")
            buffer.seek(0)

            logger.debug(f"라인 차트 이미지 메모리 버퍼 생성 완료, 크기: {len(buffer.getvalue())} bytes")
            return buffer
        except Exception as e:
            logger.error(f"라인 차트 이미지 생성 오류: {str(e)}")
            return None
        finally:
            try:
                # 원래 폰트 설정 복원
                plt.rcParams["font.family"] = original_font_family
                plt.rcParams["axes.unicode_minus"] = original_unicode_minus
                plt.close("all")
            except Exception as cleanup_error:
                logger.error(f"라인차트 matplotlib 리소스 정리 실패: {cleanup_error}")
                raise cleanup_error

    def _create_mixed_chart_image(self, component: Dict[str, Any]) -> io.BytesIO:
        """혼합 차트 컴포넌트를 이미지로 변환하여 메모리 버퍼로 반환합니다."""
        try:
            data = component.get("data", {})
            title = component.get("title", "혼합 차트")
            labels = data.get("labels", [])
            bar_datasets = data.get("bar_datasets", [])
            line_datasets = data.get("line_datasets", [])
            y_axis_left_title = data.get("y_axis_left_title", "값")
            y_axis_right_title = data.get("y_axis_right_title", "비율")

            if not labels or (not bar_datasets and not line_datasets):
                return None

            # 한글 폰트 설정 (차트 생성 전에 먼저 설정)
            original_font_family = plt.rcParams.get("font.family", [])
            original_unicode_minus = plt.rcParams.get("axes.unicode_minus", True)

            try:
                # NanumGothic 폰트 시도
                font_path = Path(__file__).parent.parent.parent / "resource" / "fonts" / "NanumGothic.ttf"
                if font_path.exists():
                    # matplotlib 폰트 매니저에 등록
                    fm.fontManager.addfont(str(font_path))
                    plt.rcParams["font.family"] = "NanumGothic"
                    plt.rcParams["axes.unicode_minus"] = False
                else:
                    # 시스템 기본 한글 폰트 시도
                    available_fonts = [font.name for font in fm.fontManager.ttflist]
                    korean_fonts = ["Malgun Gothic", "AppleGothic", "Noto Sans CJK KR", "Arial Unicode MS"]

                    font_found = False
                    for font_name in korean_fonts:
                        if font_name in available_fonts:
                            plt.rcParams["font.family"] = font_name
                            plt.rcParams["axes.unicode_minus"] = False
                            font_found = True
                            break

                    if not font_found:
                        # 한글이 포함된 제목을 영문으로 대체
                        title = "Mixed Chart"
                        y_axis_left_title = "Value"
                        y_axis_right_title = "Ratio"

            except Exception as font_error:
                logger.error(f"혼합차트 폰트 설정 실패: {font_error}")
                raise font_error

            fig, ax1 = plt.subplots(figsize=(12, 6))

            if bar_datasets:
                x = np.arange(len(labels))
                width = 0.8 / len(bar_datasets)
                for i, dataset in enumerate(bar_datasets):
                    bars = ax1.bar(x + i * width, dataset.get("data", []), width, label=dataset.get("label"), color=dataset.get("backgroundColor", f"C{i}"), alpha=0.7)
                    for bar, value in zip(bars, dataset.get("data", [])):
                        height = bar.get_height()
                        ax1.text(
                            bar.get_x() + bar.get_width() / 2.0,
                            height,
                            f"{value:,.0f}" if isinstance(value, (int, float)) else str(value),
                            ha="center",
                            va="bottom",
                            fontsize=10,
                        )
                ax1.set_xlabel("", fontsize=12)
                ax1.set_ylabel(y_axis_left_title, fontsize=12, color="black")
                ax1.set_xticks(x + width * (len(bar_datasets) - 1) / 2)
                ax1.set_xticklabels(labels, rotation=45, ha="right")
                ax1.tick_params(axis="y", which="major", labelsize=12)

            if line_datasets:
                ax2 = ax1.twinx()
                for i, dataset in enumerate(line_datasets):
                    ax2.plot(
                        labels,
                        dataset.get("data", []),
                        label=dataset.get("label"),
                        color=dataset.get("borderColor", f"C{len(bar_datasets) + i}"),
                        linestyle="--",
                        linewidth=2,
                        marker="o",
                        markersize=4,
                    )
                ax2.set_ylabel(y_axis_right_title, fontsize=12, color="black")
                ax2.tick_params(axis="y", which="major", labelsize=12)

            ax1.set_title(title, fontsize=16, fontweight="bold", pad=20)
            lines1, labels1 = ax1.get_legend_handles_labels()
            if line_datasets:
                lines2, labels2 = ax2.get_legend_handles_labels()
                ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left", fontsize=12)
            else:
                ax1.legend(fontsize=12)
            ax1.grid(True, alpha=0.3, axis="y")
            ax1.tick_params(axis="x", which="major", labelsize=12)

            # x축 레이블이 날짜 형식인지 확인하고 포맷 적용
            try:
                # 첫 번째 레이블로 날짜 형식 확인
                if labels and ("-" in str(labels[0]) and len(str(labels[0])) >= 8):
                    # 날짜 형식으로 변환하여 x축 포맷 설정
                    import matplotlib.dates as mdates

                    # 레이블을 datetime 객체로 변환
                    date_labels = []
                    for label in labels:
                        try:
                            date_obj = pd.to_datetime(label)
                            date_labels.append(date_obj)
                        except:
                            break

                    if len(date_labels) == len(labels):  # 모든 레이블이 날짜 형식
                        # 날짜 포맷 설정
                        ax1.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
                        plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45, ha="right")
            except Exception as date_format_error:
                logger.debug(f"혼합차트 날짜 포맷 적용 실패: {date_format_error}")

            plt.tight_layout()

            buffer = io.BytesIO()
            plt.savefig(buffer, format="png", dpi=300, bbox_inches="tight", facecolor="white", edgecolor="none")
            buffer.seek(0)

            logger.debug(f"혼합 차트 이미지 메모리 버퍼 생성 완료, 크기: {len(buffer.getvalue())} bytes")
            return buffer
        except Exception as e:
            logger.error(f"혼합 차트 이미지 생성 오류: {str(e)}")
            return None
        finally:
            try:
                # 원래 폰트 설정 복원
                plt.rcParams["font.family"] = original_font_family
                plt.rcParams["axes.unicode_minus"] = original_unicode_minus
                plt.close("all")
            except Exception as cleanup_error:
                logger.error(f"혼합차트 matplotlib 리소스 정리 실패: {cleanup_error}")
                raise cleanup_error

    def _create_price_chart_image(self, component: Dict[str, Any]) -> io.BytesIO:
        """주가 차트 컴포넌트를 mplfinance를 사용하여 이미지로 변환하여 메모리 버퍼로 반환합니다."""
        try:
            data = component.get("data", {})
            title = component.get("title", "주가 차트")
            symbol = data.get("symbol", "")
            name = data.get("name", "")
            candle_data = data.get("candle_data", [])

            if not candle_data:
                return None

                # 한글 폰트 설정 및 폰트 경로 준비
            original_font_family = plt.rcParams.get("font.family", [])
            original_unicode_minus = plt.rcParams.get("axes.unicode_minus", True)
            font_prop = None
            use_korean = True

            try:
                # NanumGothic 폰트 시도
                font_path = Path(__file__).parent.parent.parent / "resource" / "fonts" / "NanumGothic.ttf"
                if font_path.exists():
                    # matplotlib 폰트 매니저에 등록하고 FontProperties 생성
                    fm.fontManager.addfont(str(font_path))
                    font_prop = fm.FontProperties(fname=str(font_path))
                    plt.rcParams["font.family"] = "NanumGothic"
                    plt.rcParams["axes.unicode_minus"] = False
                    logger.debug("mplfinance에 NanumGothic 폰트 설정 완료")
                else:
                    # 시스템 기본 한글 폰트 시도
                    available_fonts = [font.name for font in fm.fontManager.ttflist]
                    korean_fonts = ["Malgun Gothic", "AppleGothic", "Noto Sans CJK KR", "Arial Unicode MS"]

                    for font_name in korean_fonts:
                        if font_name in available_fonts:
                            font_prop = fm.FontProperties(family=font_name)
                            plt.rcParams["font.family"] = font_name
                            plt.rcParams["axes.unicode_minus"] = False
                            logger.debug(f"mplfinance에 {font_name} 폰트 설정 완료")
                            break

            except Exception as font_error:
                logger.error(f"mplfinance 폰트 설정 실패: {font_error}")
                raise font_error

            # 데이터를 pandas DataFrame으로 변환 및 거래량 색상 계산
            df_data = []
            volume_colors = []

            for i, item in enumerate(candle_data):
                current_volume = int(item["volume"])
                prev_volume = int(candle_data[i - 1]["volume"]) if i > 0 else current_volume

                # 전일 대비 거래량 증감에 따른 색상 결정
                if current_volume > prev_volume:
                    volume_colors.append("red")  # 거래량 증가 시 빨간색
                elif current_volume < prev_volume:
                    volume_colors.append("blue")  # 거래량 감소 시 파란색
                else:
                    volume_colors.append("gray")  # 거래량 변화 없음 시 회색

                # 사용자가 제공한 "YYYY-MM-DD" 형식으로 날짜를 변환합니다.
                time_val = item["time"]
                try:
                    # 여러 날짜 형식을 시도해서 변환
                    if isinstance(time_val, str):
                        # ISO 형식 또는 기본 형식 시도
                        date_obj = pd.to_datetime(time_val, errors="raise")
                    else:
                        # 숫자나 다른 형식의 경우
                        date_obj = pd.to_datetime(time_val, errors="raise")

                except Exception as date_error:
                    logger.error(f"주가차트(candle) 날짜 변환 실패: '{time_val}', 오류: {date_error}. 기본 날짜로 대체.")
                    # 현재 날짜가 아닌 기본 날짜를 사용 (인덱스 기반)
                    date_obj = pd.to_datetime(f"2024-01-{i + 1:02d}", errors="coerce")

                df_data.append(
                    {
                        "Date": date_obj,
                        "Open": float(item["open"]),
                        "High": float(item["high"]),
                        "Low": float(item["low"]),
                        "Close": float(item["close"]),
                        "Volume": current_volume,
                    }
                )

            df = pd.DataFrame(df_data)

            # 날짜가 올바르게 변환되었는지 확인
            if df["Date"].isna().any():
                # NaT 값을 제거하거나 대체
                df = df.dropna(subset=["Date"])

            df.set_index("Date", inplace=True)

            # 지지선/저항선 준비
            hlines = {}
            support_lines = data.get("support_lines", [])
            resistance_lines = data.get("resistance_lines", [])

            # 모든 지지선과 저항선 가격을 수집
            line_prices = []
            line_colors = []
            line_styles = []

            for support in support_lines:
                price = support.get("price", 0)
                line_prices.append(price)
                line_colors.append("green")
                line_styles.append("--")

            for resistance in resistance_lines:
                price = resistance.get("price", 0)
                line_prices.append(price)
                line_colors.append("red")
                line_styles.append("--")

            # hlines 형식 맞추기 (mplfinance 요구사항에 따라)
            if line_prices:
                hlines = dict(hlines=line_prices, colors=line_colors, linestyle=line_styles, linewidths=2)

            # mplfinance 스타일 설정 (한국 주식 시장 관례: 상승=빨간색, 하락=파란색)
            mc = mpf.make_marketcolors(
                up="r",  # 상승 시 빨간색
                down="b",  # 하락 시 파란색
                edge="inherit",
                wick={"up": "red", "down": "blue"},  # 캔들 심지도 동일한 색상
                volume="in",  # 거래량은 별도로 처리
            )
            s = mpf.make_mpf_style(marketcolors=mc, gridstyle="-", gridcolor="lightgray", facecolor="white", figcolor="white")

            # 거래량을 별도 addplot으로 생성 (색상 제어를 위해)
            volume_addplot = mpf.make_addplot(
                df["Volume"],
                type="bar",
                panel=1,  # 별도 패널
                color=volume_colors,  # 전일 대비 증감 색상
                alpha=0.8,
                width=0.8,
                secondary_y=False,
            )

            # 차트 생성 (제목과 레이블은 나중에 수동 설정)
            plot_kwargs = {
                "data": df,
                "type": "candle",
                "style": s,
                "volume": False,  # 기본 거래량 끄고 addplot 사용
                "addplot": [volume_addplot],  # 커스텀 거래량 추가
                "figsize": (12, 8),
                "returnfig": True,
            }

            # hlines가 있는 경우에만 추가
            if line_prices:
                plot_kwargs["hlines"] = hlines

            try:
                fig, axes = mpf.plot(**plot_kwargs)
            except Exception as plot_error:
                logger.error(f"주가차트 mplfinance 호출 실패: {plot_error}")
                raise

            # x축 날짜 포맷을 숫자 형식으로 설정 (2024-06-18)

            # mplfinance 기본 날짜 형식 사용 (x축 날짜 형식 처리 제거)

            # 거래량 색상은 addplot에서 직접 처리되므로 별도 작업 불필요
            logger.debug(f"주가차트: 거래량 색상 addplot으로 처리 완료, 색상 개수={len(volume_colors)}")

            # 한글 폰트로 제목과 레이블 수동 설정
            if use_korean and font_prop:
                try:
                    # 메인 차트 (가격)
                    axes[0].set_title(f"{title} - {name}({symbol})", fontproperties=font_prop, fontsize=16, fontweight="bold")
                    axes[0].set_ylabel("주가(원)", fontproperties=font_prop, fontsize=14)

                    # 거래량 차트
                    if len(axes) > 1:
                        axes[1].set_ylabel("거래량", fontproperties=font_prop, fontsize=14)
                        axes[1].set_xlabel("날짜", fontproperties=font_prop, fontsize=14)
                except Exception as font_apply_error:
                    logger.error(f"한글 폰트 수동 적용 실패: {font_apply_error}")
                    raise font_apply_error

            # 메모리 버퍼에 저장
            buffer = io.BytesIO()
            fig.savefig(buffer, format="png", dpi=300, bbox_inches="tight", facecolor="white", edgecolor="none")
            buffer.seek(0)

            logger.debug(f"mplfinance 주가 차트 이미지 메모리 버퍼 생성 완료, 크기: {len(buffer.getvalue())} bytes")
            return buffer

        except Exception as e:
            logger.error(f"mplfinance 주가 차트 이미지 생성 오류: {str(e)}")
            return None
        finally:
            try:
                # 원래 폰트 설정 복원
                plt.rcParams["font.family"] = original_font_family
                plt.rcParams["axes.unicode_minus"] = original_unicode_minus
                plt.close("all")
            except Exception as cleanup_error:
                logger.error(f"가격차트 matplotlib 리소스 정리 실패: {cleanup_error}")
                raise cleanup_error

    def _create_technical_indicator_chart_image(self, component: Dict[str, Any]) -> io.BytesIO:
        """기술적 지표 차트 컴포넌트를 mplfinance만 사용하여 이미지로 변환하여 메모리 버퍼로 반환합니다."""
        from matplotlib.lines import Line2D  # 범례 생성용 import

        try:
            data = component.get("data", {})
            title = component.get("title", "기술적 지표 차트")
            symbol = data.get("symbol", "")
            name = data.get("name", "")
            dates = data.get("dates", [])
            indicators = data.get("indicators", [])
            candle_data = data.get("candle_data", [])

            if not dates or not indicators:
                return None

            # 한글 폰트 설정
            original_font_family = plt.rcParams.get("font.family", [])
            original_unicode_minus = plt.rcParams.get("axes.unicode_minus", True)
            font_prop = None
            use_korean = True

            try:
                font_path = Path(__file__).parent.parent.parent / "resource" / "fonts" / "NanumGothic.ttf"
                if font_path.exists():
                    fm.fontManager.addfont(str(font_path))
                    font_prop = fm.FontProperties(fname=str(font_path))
                    plt.rcParams["font.family"] = "NanumGothic"
                    plt.rcParams["axes.unicode_minus"] = False
                else:
                    use_korean = False
                    title = "Technical Indicators"
                    name = "Stock"
            except Exception:
                use_korean = False
                title = "Technical Indicators"
                name = "Stock"

            # 캔들 데이터가 있으면 사용, 없으면 더미 데이터 생성
            volume_colors = []
            if candle_data and len(candle_data) > 0:
                df_data = []
                for i, item in enumerate(candle_data):
                    current_volume = int(item["volume"])
                    prev_volume = int(candle_data[i - 1]["volume"]) if i > 0 else current_volume

                    # 전일 대비 거래량 증감에 따른 색상 결정 (혹시 나중에 거래량 표시할 경우를 대비)
                    if current_volume > prev_volume:
                        volume_colors.append("red")  # 거래량 증가 시 빨간색
                    elif current_volume < prev_volume:
                        volume_colors.append("blue")  # 거래량 감소 시 파란색
                    else:
                        volume_colors.append("gray")  # 거래량 변화 없음 시 회색

                    # 날짜 변환 - "2024-09-24" 형식 처리
                    time_str = item["time"]
                    try:
                        # 문자열 날짜 형식 (YYYY-MM-DD)
                        date_obj = pd.to_datetime(time_str, format="%Y-%m-%d")
                        logger.debug(f"기술적지표 날짜 변환 성공: {time_str} -> {date_obj}")
                    except Exception as date_error:
                        logger.warning(f"기술적지표 날짜 변환 실패: {time_str}, 오류: {date_error}")
                        # 다른 형식으로 시도
                        try:
                            date_obj = pd.to_datetime(time_str)
                        except:
                            # 기본값으로 현재 날짜 사용
                            date_obj = pd.Timestamp.now()

                    df_data.append(
                        {
                            "Date": date_obj,
                            "Open": float(item["open"]),
                            "High": float(item["high"]),
                            "Low": float(item["low"]),
                            "Close": float(item["close"]),
                            "Volume": current_volume,
                        }
                    )
                show_volume = False  # 기술적 지표 차트에서는 거래량 표시 안함
            else:
                # 더미 캔들 데이터 생성
                df_data = []
                for i, date_str in enumerate(dates):
                    dummy_price = 100 + i * 0.1

                    # 사용자가 제공한 "YYYY-MM-DD" 형식으로 날짜를 변환합니다.
                    time_val = date_str
                    try:
                        date_obj = pd.to_datetime(time_val, format="%Y-%m-%d", errors="raise")
                    except Exception as date_error:
                        logger.error(f"기술적 지표 차트(dummy) 날짜 변환 실패: '{time_val}', 오류: {date_error}. 현재 날짜로 대체.")
                        date_obj = pd.to_datetime("now") + pd.Timedelta(days=i)

                    df_data.append(
                        {
                            "Date": date_obj,
                            "Open": dummy_price,
                            "High": dummy_price + 0.5,
                            "Low": dummy_price - 0.5,
                            "Close": dummy_price + 0.1,
                            "Volume": 1000,
                        }
                    )
                show_volume = False

            df = pd.DataFrame(df_data)
            df.set_index("Date", inplace=True)

            # mplfinance 스타일 설정
            mc = mpf.make_marketcolors(
                up="r",
                down="b",
                edge="inherit",
                wick={"up": "red", "down": "blue"},
                volume="in",  # 거래량 색상은 나중에 수동 설정 (현재는 거래량 표시 안함)
            )
            s = mpf.make_mpf_style(
                marketcolors=mc, gridstyle="-", gridcolor="lightgray", facecolor="white", figcolor="white", rc={"font.size": 12, "xtick.labelsize": 12, "ytick.labelsize": 12}
            )

            # 지표 addplot 준비 - 지표 유형에 따라 다른 패널 할당
            addplot_list = []
            # 백엔드와 일치하는 기본 색상 배열 (추세추종 지표용)
            default_colors = ["#3b82f6", "#10b981", "#ef4444", "#f59e0b", "#e91e63", "#6554c0"]
            has_rsi_indicators = False
            has_oscillator_indicators = False
            has_trend_indicators = False

            for i, indicator in enumerate(indicators):
                indicator_data = indicator.get("data", [])
                indicator_name = indicator.get("name", "").lower()

                if len(indicator_data) == len(df):
                    # 백엔드에서 설정한 색상을 우선 사용
                    color = indicator.get("color", default_colors[i % len(default_colors)])
                    line_style = "-" if indicator.get("line_style") == "solid" else "--"

                    # SuperTrend는 주가와 같은 패널 (panel 0)
                    if "supertrend" in indicator_name or "슈퍼트렌드" in indicator_name:
                        # SuperTrend는 주가와 같은 스케일, 오른쪽 y축 사용
                        addplot_list.append(
                            mpf.make_addplot(
                                indicator_data,
                                panel=0,  # 캔들차트와 같은 패널
                                color=color,
                                linestyle=line_style,
                                width=2,
                                secondary_y=False,  # 오른쪽 y축 (주가와 함께)
                            )
                        )
                    elif "rsi" in indicator_name:
                        # RSI는 전용 패널 (panel 1) - 0-100 스케일
                        addplot_list.append(
                            mpf.make_addplot(
                                indicator_data,
                                panel=1,  # RSI 전용 패널
                                color=color,
                                linestyle=line_style,
                                width=2,
                                secondary_y=False,
                            )
                        )
                        has_rsi_indicators = True
                    elif "macd" in indicator_name or "momentum" in indicator_name or "williams" in indicator_name or "stochastic" in indicator_name:
                        # MACD 등 모멘텀 지표는 별도 패널 (panel 2)
                        panel_num = 2 if has_rsi_indicators else 1
                        addplot_list.append(
                            mpf.make_addplot(
                                indicator_data,
                                panel=panel_num,  # 모멘텀 지표 패널
                                color=color,
                                linestyle=line_style,
                                width=2,
                                secondary_y=False,
                            )
                        )
                        has_oscillator_indicators = True
                    else:
                        # ADX, +DI, -DI 등 추세 지표는 별도 패널
                        if has_rsi_indicators and has_oscillator_indicators:
                            panel_num = 3
                        elif has_rsi_indicators or has_oscillator_indicators:
                            panel_num = 2
                        else:
                            panel_num = 1

                        addplot_list.append(
                            mpf.make_addplot(
                                indicator_data,
                                panel=panel_num,  # 추세 지표 패널
                                color=color,
                                linestyle=line_style,
                                width=2,
                                secondary_y=False,
                            )
                        )
                        has_trend_indicators = True

            # 패널 수 계산 및 비율 설정
            total_indicator_panels = sum([has_rsi_indicators, has_oscillator_indicators, has_trend_indicators])

            if total_indicator_panels > 0:
                if show_volume:
                    if total_indicator_panels == 1:
                        panel_ratios = (3, 2, 1)  # 주가:지표:거래량
                    elif total_indicator_panels == 2:
                        panel_ratios = (3, 1, 1, 1)  # 주가:지표1:지표2:거래량
                    else:  # 3개 이상
                        panel_ratios = (3, 1, 1, 1, 1)  # 주가:지표1:지표2:지표3:거래량
                else:
                    if total_indicator_panels == 1:
                        panel_ratios = (2, 1)  # 주가:지표
                    elif total_indicator_panels == 2:
                        panel_ratios = (2, 1, 1)  # 주가:지표1:지표2
                    else:  # 3개 이상
                        panel_ratios = (2, 1, 1, 1)  # 주가:지표1:지표2:지표3
            else:
                if show_volume:
                    panel_ratios = (3, 1)  # 주가:거래량
                else:
                    panel_ratios = (1,)  # 주가만

            # 차트 생성
            plot_kwargs = {
                "data": df,
                "type": "candle",
                "style": s,
                "volume": show_volume,
                "figsize": (12, 10),
                "panel_ratios": panel_ratios,
                "returnfig": True,
            }

            if len(addplot_list) > 0:
                plot_kwargs["addplot"] = addplot_list

            fig, axes = mpf.plot(**plot_kwargs)
            # mplfinance 기본 날짜 형식 사용 (x축 날짜 처리 제거)

            # 제목과 레이블 설정
            if use_korean and font_prop:
                try:
                    axes[0].set_title(f"{title} - {name}({symbol})", fontproperties=font_prop, fontsize=16, fontweight="bold")
                    axes[0].set_ylabel("주가(원)", fontproperties=font_prop, fontsize=14)

                    # 각 지표 패널에 대한 Y축 레이블 설정
                    panel_idx = 1

                    # RSI 패널 설정
                    if has_rsi_indicators and len(axes) > panel_idx:
                        axes[panel_idx].set_ylabel("RSI", fontproperties=font_prop, fontsize=14)
                        axes[panel_idx].set_ylim(0, 100)
                        axes[panel_idx].axhline(y=70, color="red", linestyle="--", alpha=0.5, linewidth=1)
                        axes[panel_idx].axhline(y=30, color="blue", linestyle="--", alpha=0.5, linewidth=1)
                        panel_idx += 1

                    # 모멘텀 지표 패널 설정 (MACD 등)
                    if has_oscillator_indicators and len(axes) > panel_idx:
                        axes[panel_idx].set_ylabel("", fontproperties=font_prop, fontsize=14)
                        panel_idx += 1

                    # 추세 지표 패널 설정 (ADX 등)
                    if has_trend_indicators and len(axes) > panel_idx:
                        axes[panel_idx].set_ylabel("추세 지표", fontproperties=font_prop, fontsize=14)
                        panel_idx += 1

                    # 거래량 패널
                    if show_volume and len(axes) > panel_idx:
                        axes[panel_idx].set_ylabel("거래량", fontproperties=font_prop, fontsize=14)
                        axes[panel_idx].set_xlabel("날짜", fontproperties=font_prop, fontsize=14)
                    else:
                        axes[-1].set_xlabel("날짜", fontproperties=font_prop, fontsize=14)

                except Exception as e:
                    logger.warning(f"한글 폰트 적용 실패: {e}")
                    axes[0].set_title(f"Technical Indicators - {name}({symbol})", fontsize=16, fontweight="bold")
                    axes[0].set_ylabel("Price (KRW)", fontsize=14)

                    # 각 지표 패널에 대한 Y축 레이블 설정 (영어 버전)
                    panel_idx = 1

                    # RSI 패널 설정
                    if has_rsi_indicators and len(axes) > panel_idx:
                        axes[panel_idx].set_ylabel("RSI", fontsize=14)
                        axes[panel_idx].set_ylim(0, 100)
                        axes[panel_idx].axhline(y=70, color="red", linestyle="--", alpha=0.5, linewidth=1)
                        axes[panel_idx].axhline(y=30, color="blue", linestyle="--", alpha=0.5, linewidth=1)
                        panel_idx += 1

                    # 모멘텀 지표 패널 설정 (MACD 등)
                    if has_oscillator_indicators and len(axes) > panel_idx:
                        axes[panel_idx].set_ylabel("Momentum Indicators", fontsize=14)
                        panel_idx += 1

                    # 추세 지표 패널 설정 (ADX 등)
                    if has_trend_indicators and len(axes) > panel_idx:
                        axes[panel_idx].set_ylabel("Trend Indicators", fontsize=14)
                        panel_idx += 1
            else:
                axes[0].set_title(f"Technical Indicators - {name}({symbol})", fontsize=16, fontweight="bold")
                axes[0].set_ylabel("Price (KRW)", fontsize=14)

                # 각 지표 패널에 대한 Y축 레이블 설정 (영어 버전)
                panel_idx = 1

                # RSI 패널 설정
                if has_rsi_indicators and len(axes) > panel_idx:
                    axes[panel_idx].set_ylabel("RSI", fontsize=14)
                    axes[panel_idx].set_ylim(0, 100)
                    axes[panel_idx].axhline(y=70, color="red", linestyle="--", alpha=0.5, linewidth=1)
                    axes[panel_idx].axhline(y=30, color="blue", linestyle="--", alpha=0.5, linewidth=1)
                    panel_idx += 1

                # 모멘텀 지표 패널 설정 (MACD 등)
                if has_oscillator_indicators and len(axes) > panel_idx:
                    axes[panel_idx].set_ylabel("Momentum Indicators", fontsize=14)
                    panel_idx += 1

                # 추세 지표 패널 설정 (ADX 등)
                if has_trend_indicators and len(axes) > panel_idx:
                    axes[panel_idx].set_ylabel("Trend Indicators", fontsize=14)
                    panel_idx += 1

                if show_volume and len(axes) > panel_idx:
                    axes[panel_idx].set_ylabel("Volume", fontsize=14)
                    axes[panel_idx].set_xlabel("Date", fontsize=14)
                else:
                    axes[-1].set_xlabel("Date", fontsize=14)

            # 모든 지표 범례를 차트 맨 아래에 표시 (색상 일치를 위해 수동 생성)
            if len(addplot_list) > 0:
                legend_elements = []
                legend_labels = []

                for indicator in indicators:
                    if indicator.get("data"):
                        # 각 지표의 이름과 색상을 가져와서 범례 요소 생성
                        indicator_name = indicator.get("name", "")
                        indicator_color = indicator.get("color", "#3b82f6")  # 기본 색상

                        # matplotlib Line2D 객체로 범례 요소 생성
                        legend_elements.append(Line2D([0], [0], color=indicator_color, lw=2, label=indicator_name))
                        legend_labels.append(indicator_name)

                if legend_elements:
                    # 범례를 Figure 레벨에서 차트 아래쪽에 표시
                    if use_korean and font_prop:
                        fig.legend(
                            handles=legend_elements,
                            labels=legend_labels,
                            loc="lower center",
                            bbox_to_anchor=(0.5, -0.02),
                            ncol=min(len(legend_elements), 4),
                            prop=font_prop,
                            fontsize=11,
                        )
                    else:
                        fig.legend(handles=legend_elements, labels=legend_labels, loc="lower center", bbox_to_anchor=(0.5, -0.02), ncol=min(len(legend_elements), 4), fontsize=11)

            # 메모리 버퍼에 저장
            buffer = io.BytesIO()
            fig.savefig(buffer, format="png", dpi=300, bbox_inches="tight", facecolor="white", edgecolor="none")
            buffer.seek(0)

            return buffer

        except Exception as e:
            logger.error(f"기술적 지표 차트 이미지 생성 오류: {str(e)}")
            return None
        finally:
            try:
                plt.rcParams["font.family"] = original_font_family
                plt.rcParams["axes.unicode_minus"] = original_unicode_minus
                plt.close("all")
            except Exception as cleanup_error:
                logger.error(f"기술적 지표 차트 정리 작업 실패: {cleanup_error}")
                raise cleanup_error

    def _create_chart_image(self, component: Dict[str, Any]) -> Optional[io.BytesIO]:
        """차트 타입에 따라 적절한 이미지 생성 함수를 호출합니다."""
        component_type = component.get("type", "")
        chart_creators = {
            "bar_chart": self._create_bar_chart_image,
            "line_chart": self._create_line_chart_image,
            "mixed_chart": self._create_mixed_chart_image,
            "price_chart": self._create_price_chart_image,
            "technical_indicator_chart": self._create_technical_indicator_chart_image,
        }
        creator = chart_creators.get(component_type)
        if creator:
            return creator(component)

        logger.warning(f"지원하지 않는 차트 타입 '{component_type}'의 이미지 생성을 건너뜁니다.")
        return None

    def _convert_components_to_pdf_elements(self, components: List[Dict[str, Any]], styles):
        """컴포넌트들을 PDF 요소로 변환합니다."""
        elements = []
        i = 0
        while i < len(components):
            component = components[i]
            component_type = component.get("type", "")

            # 바차트 또는 혼합차트 2열 배치 처리
            if component_type in ["bar_chart", "mixed_chart"]:
                # 현재 위치에서부터 연속된 바/혼합 차트 찾기
                chart_group = [component]
                j = i + 1
                while j < len(components) and components[j].get("type") in ["bar_chart", "mixed_chart"]:
                    chart_group.append(components[j])
                    j += 1

                # 차트 그룹을 2개씩 짝지어 처리
                for k in range(0, len(chart_group), 2):
                    pair = chart_group[k : k + 2]

                    if len(pair) == 2:
                        # 차트 2개를 한 행에 배치
                        c1, c2 = pair[0], pair[1]

                        title1 = Paragraph(c1.get("title", ""), styles["Heading4-KO"])
                        title2 = Paragraph(c2.get("title", ""), styles["Heading4-KO"])

                        img_buffer1 = self._create_chart_image(c1)
                        img_buffer2 = self._create_chart_image(c2)

                        if img_buffer1:
                            img1 = Image(img_buffer1)
                            # 2열 배치이므로 최대 너비를 8.5cm로 제한하고 비율 유지
                            img1.drawHeight = img1.drawHeight * 8.5 * cm / img1.drawWidth if img1.drawWidth > 8.5 * cm else img1.drawHeight
                            img1.drawWidth = min(img1.drawWidth, 8.5 * cm)
                        else:
                            img1 = Paragraph("차트1 생성 실패", styles["Normal-KO"])

                        if img_buffer2:
                            img2 = Image(img_buffer2)
                            # 2열 배치이므로 최대 너비를 8.5cm로 제한하고 비율 유지
                            img2.drawHeight = img2.drawHeight * 8.5 * cm / img2.drawWidth if img2.drawWidth > 8.5 * cm else img2.drawHeight
                            img2.drawWidth = min(img2.drawWidth, 8.5 * cm)
                        else:
                            img2 = Paragraph("차트2 생성 실패", styles["Normal-KO"])

                        chart_table_data = [[title1, title2], [img1, img2]]
                        chart_table = Table(chart_table_data, colWidths=[9 * cm, 9 * cm])
                        chart_table.setStyle(
                            TableStyle(
                                [
                                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                                ]
                            )
                        )
                        elements.append(chart_table)
                        elements.append(Spacer(1, 12))

                    elif len(pair) == 1:
                        # 남은 차트 1개는 중앙에 단독 배치
                        chart_component = pair[0]
                        chart_title = chart_component.get("title", "차트")
                        image_buffer = self._create_chart_image(chart_component)

                        if image_buffer:
                            elements.append(Paragraph(chart_title, styles["Heading3-KO"]))
                            elements.append(Spacer(1, 6))
                            # 단독 배치 차트도 비율 유지
                            img = Image(image_buffer)
                            img.drawHeight = img.drawHeight * 16 * cm / img.drawWidth if img.drawWidth > 16 * cm else img.drawHeight
                            img.drawWidth = min(img.drawWidth, 16 * cm)
                            elements.append(img)
                            elements.append(Spacer(1, 12))
                        else:
                            elements.append(Paragraph(f"[{chart_title}] - 차트 이미지 생성 실패", styles["Normal-KO"]))

                i = j  # 다음 컴포넌트로 이동
                continue

            # 기타 컴포넌트 처리
            if component_type == "heading":
                level = component.get("level", 1)
                content = component.get("content", "")
                style_name = f"Heading{min(level, 6)}-KO"

                # 최상위 헤더(숫자로 시작하는 헤더나 level 1) 위에 여백 추가
                is_top_level_header = False
                is_sub_level_header = False

                if level == 2:  # 1. 핵심 요약 등의 level은 2이다.
                    is_top_level_header = True
                elif level == 3:  # 1.1. 핵심 요약 등의 level은 3이다.
                    is_sub_level_header = True

                # 최상위 헤더이고 이미 요소가 있는 경우 (첫 번째 헤더가 아닌 경우) 위쪽에 여백 추가
                if is_top_level_header and elements:
                    elements.append(Spacer(1, 20))  # 20pt 여백 추가
                elif is_sub_level_header and elements:
                    elements.append(Spacer(1, 10))  # 10pt 여백 추가

                elements.append(Paragraph(content, styles[style_name]))
                elements.append(Spacer(1, 3))

            elif component_type == "paragraph":
                content = component.get("content", "")

                # 마크다운을 HTML로 변환하고 <b> 태그를 ReportLab용 폰트 태그로 변환
                html_content = convert_markdown_to_html(content)

                # 단락 컴포넌트이므로 <p> 태그는 제거
                html_content = html_content.strip()
                if html_content.startswith("<p>") and html_content.endswith("</p>"):
                    html_content = html_content[3:-4]

                html_content = html_content.replace("<b>", '<font face="NanumGothicBold">').replace("</b>", "</font>")

                elements.append(Paragraph(html_content, styles["Paragraph-KO"]))  # 들여쓰기 적용된 스타일 사용
                elements.append(Spacer(1, 4))

            elif component_type == "list":
                ordered = component.get("ordered", False)
                items = component.get("items", [])
                for idx, item in enumerate(items):
                    item_content = item.get("content", "") if isinstance(item, dict) else str(item)

                    # 리스트 항목 내 마크다운을 HTML로 변환
                    html_item = convert_markdown_to_html(item_content)

                    # <p> 태그 제거
                    html_item = html_item.strip()
                    if html_item.startswith("<p>") and html_item.endswith("</p>"):
                        html_item = html_item[3:-4]

                    # <b> 태그를 reportlab용 폰트 태그로 변환
                    html_item = html_item.replace("<b>", '<font face="NanumGothicBold">').replace("</b>", "</font>")

                    bullet = f"{idx + 1}. " if ordered else "• "
                    elements.append(Paragraph(bullet + html_item, styles["ListItem-KO"]))
                elements.append(Spacer(1, 6))

            elif component_type == "table":
                table_data = component.get("data", {})
                headers = table_data.get("headers", [])
                rows = table_data.get("rows", [])
                table_title = component.get("title")

                if table_title:
                    elements.append(Paragraph(table_title, styles["Heading3-KO"]))
                    elements.append(Spacer(1, 4))

                if headers and rows:
                    header_row = [h.get("label", "") for h in headers]
                    table_rows = [header_row] + [[str(row.get(h.get("key", ""), "")) for h in headers] for row in rows]

                    if table_rows:
                        col_width = 450 / max(1, len(table_rows[0]))
                        wrapped_table = [[Paragraph(str(cell), styles["Heading5-KO" if r == 0 else "Normal-KO"]) for cell in row] for r, row in enumerate(table_rows)]
                        table = Table(wrapped_table, colWidths=[col_width] * len(table_rows[0]))
                        table.setStyle(
                            TableStyle(
                                [
                                    ("FONTNAME", (0, 0), (-1, -1), "NanumGothic"),
                                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                                    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                                ]
                            )
                        )
                        elements.append(table)
                        elements.append(Spacer(1, 8))

            elif component_type in ["line_chart", "price_chart", "technical_indicator_chart"]:
                # 이 차트들은 단독으로 전체 너비 사용
                chart_title = component.get("title", "차트")
                image_buffer = self._create_chart_image(component)

                if image_buffer:
                    elements.append(Paragraph(chart_title, styles["Heading3-KO"]))
                    elements.append(Spacer(1, 6))
                    try:
                        # 이미지 원본 크기 유지하면서 PDF 페이지에 맞게 조정
                        img = Image(image_buffer)
                        img.drawHeight = img.drawHeight * 16 * cm / img.drawWidth if img.drawWidth > 16 * cm else img.drawHeight
                        img.drawWidth = min(img.drawWidth, 16 * cm)
                        elements.append(img)
                        elements.append(Spacer(1, 12))
                        logger.debug(f"{component_type} 이미지 PDF 추가 완료 (비율 유지, 크기: {img.drawWidth:.1f}x{img.drawHeight:.1f})")
                    except Exception as img_error:
                        logger.error(f"{component_type} 이미지 PDF 추가 실패, 오류: {str(img_error)}")
                        elements.append(Paragraph(f"[{chart_title}] - 차트 이미지를 PDF에 추가할 수 없습니다.", styles["Normal-KO"]))
                else:
                    logger.warning(f"차트 이미지 생성 실패: {component_type}, 제목: {chart_title}")
                    elements.append(Paragraph(f"[{chart_title}] - 차트 이미지를 생성할 수 없습니다.", styles["Normal-KO"]))
                    elements.append(Spacer(1, 6))

            else:
                if component_type not in ["bar_chart", "mixed_chart"]:  # 이미 처리됨
                    logger.warning(f"알 수 없는 컴포넌트 타입: {component_type}")

            i += 1

        return elements

    async def generate_chat_pdf(
        self,
        chat_session: Dict[str, Any],
        messages: List[Dict[str, Any]],
        user_id: str,
        expert_mode: bool = False,
    ) -> Dict[str, Any]:
        """
        채팅 세션과 메시지 목록을 PDF로 변환합니다.

        Args:
            chat_session: 채팅 세션 정보
            messages: 메시지 목록
            user_id: 사용자 ID
            expert_mode: 전문가 모드 사용 여부 (True: 전문가 모드, False: 주린이 모드)

        Returns:
            PDF 파일 정보 (파일명, 다운로드 URL, 만료시간)
        """
        logger.info(f"채팅 세션 '{chat_session['title']}'에 대한 PDF 생성 시작 (모드: {'전문가' if expert_mode else '주린이'})")

        # PDF 생성 작업은 CPU 바운드 작업이므로 별도 스레드에서 실행
        loop = asyncio.get_event_loop()
        pdf_buffer = await loop.run_in_executor(
            None,
            self._create_pdf_from_messages,
            chat_session,
            messages,
            expert_mode,  # 전문가 모드 여부 전달
        )

        # 파일명 설정 - 세션 ID 대신 종목명(종목코드) 사용
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_id = chat_session["id"]

        # 채팅 세션에서 종목 정보 확인
        stock_info = ""
        if chat_session.get("title"):
            stock_info = chat_session["title"]
        if chat_session.get("stock_name") and chat_session.get("stock_code"):
            # 세션 정보에 종목 정보가 있는 경우
            stock_info = f"{chat_session['stock_name']}_{chat_session['stock_code']}"
        else:
            # 세션 정보에 없으면 첫 번째 사용자 메시지에서 종목 정보 추출 시도
            for msg in messages:
                if msg["role"] == "user" and msg.get("stock_name") and msg.get("stock_code"):
                    stock_info = f"{msg['stock_name']}_{msg['stock_code']}"
                    break

        # 종목 정보가 있으면 사용, 없으면 세션 ID 사용
        if stock_info:
            # 파일명에 사용할 수 없는 특수문자 제거
            stock_info = re.sub(r'[\\/*?:"<>|]', "", stock_info)
            file_name = f"stockeasy_{stock_info}_{timestamp}.pdf"
        else:
            file_name = f"stockeasy_{session_id}_{timestamp}.pdf"

        # 임시 저장 경로 설정 (정적 파일 서빙 디렉토리에 저장)
        temp_dir = Path(settings.TEMP_DIR)
        temp_dir.mkdir(parents=True, exist_ok=True)
        temp_file_path = temp_dir / file_name

        # 파일 저장
        with open(temp_file_path, "wb") as f:
            f.write(pdf_buffer.getvalue())

        logger.info(f"PDF 파일 저장 완료: {temp_file_path}")

        # 로컬 파일 URL 생성
        # /download_chat_session은 main.py에서 설정한 정적 파일 마운트 경로
        if settings.ENV == "production":
            # 프로덕션 환경에서는 외부 도메인 사용
            base_url = "https://stockeasy.intellio.kr"
        else:
            # 개발 환경에서는 기존 설정 사용
            base_url = settings.FASTAPI_URL
        download_url = f"{base_url}/download_chat_session/{file_name}"

        # 만료 시간 설정 (24시간 - 실제로는 자동 삭제 없음)
        expires_at = (datetime.now() + timedelta(hours=24)).isoformat()

        return {"file_name": file_name, "download_url": download_url, "expires_at": expires_at}

    def _create_pdf_from_messages(
        self,
        chat_session: Dict[str, Any],
        messages: List[Dict[str, Any]],
        expert_mode: bool = False,
    ) -> io.BytesIO:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=2 * cm, leftMargin=2 * cm, topMargin=2 * cm, bottomMargin=2 * cm)
        styles = getSampleStyleSheet()
        font_name = "NanumGothic"
        bold_font = "NanumGothicBold"

        # 한글용 스타일 정의
        styles.add(ParagraphStyle(name="Normal-KO", fontName=font_name, fontSize=10, leading=14))
        styles.add(ParagraphStyle(name="BodyText-KO", parent=styles["Normal-KO"], spaceBefore=6))
        styles.add(ParagraphStyle(name="Italic-KO", parent=styles["BodyText-KO"], fontName=font_name))  # 이탤릭체는 기본 폰트 사용
        # 들여쓰기가 적용된 단락 스타일 추가
        styles.add(ParagraphStyle(name="Paragraph-KO", parent=styles["Normal-KO"], leftIndent=15, spaceBefore=3, spaceAfter=3))
        styles.add(ParagraphStyle(name="Heading1-KO", fontName=bold_font, fontSize=18, leading=22, spaceAfter=12, spaceBefore=18))
        styles.add(ParagraphStyle(name="Heading2-KO", fontName=bold_font, fontSize=16, leading=20, spaceAfter=10))
        styles.add(ParagraphStyle(name="Heading3-KO", fontName=bold_font, fontSize=14, leading=18, spaceAfter=8))
        styles.add(ParagraphStyle(name="Heading4-KO", fontName=bold_font, fontSize=12, leading=16, spaceAfter=6))
        styles.add(ParagraphStyle(name="Heading5-KO", fontName=bold_font, fontSize=10, leading=14, spaceAfter=4))
        styles.add(ParagraphStyle(name="Heading6-KO", fontName=bold_font, fontSize=9, leading=12, spaceAfter=4))
        styles.add(ParagraphStyle(name="Bullet-KO", parent=styles["Normal-KO"], firstLineIndent=0, spaceBefore=3, leftIndent=20))
        styles.add(ParagraphStyle(name="Definition-KO", parent=styles["Normal-KO"], firstLineIndent=0, leftIndent=20, spaceBefore=6, spaceAfter=2))
        styles.add(
            ParagraphStyle(
                name="Code-KO",
                fontName="Courier",
                fontSize=9,
                leading=12,
                backColor=colors.lightgrey,
                textColor=colors.darkblue,
                leftIndent=10,
                rightIndent=10,
                spaceBefore=6,
                spaceAfter=6,
            )
        )
        styles.add(ParagraphStyle(name="ListItem-KO", fontName=font_name, fontSize=10, leading=14, leftIndent=20))

        # 사용자 정의 스타일 추가
        styles.add(ParagraphStyle(name="User", fontName=bold_font, fontSize=11, leading=14, textColor=colors.darkblue, spaceAfter=4))
        styles.add(ParagraphStyle(name="Assistant", fontName=bold_font, fontSize=11, leading=14, textColor=colors.darkgreen, spaceAfter=4))
        styles.add(ParagraphStyle(name="Title-KO", fontName=bold_font, fontSize=18, leading=22, spaceAfter=12, alignment=1))  # 한글 제목 스타일

        elements = []
        elements.append(Paragraph(chat_session["title"], styles["Title-KO"]))  # 한글 제목 스타일 사용
        elements.append(Spacer(1, 12))

        for idx, message in enumerate(messages):
            if message["role"] == "status":
                continue

            role_text = "질문" if message["role"] == "user" else "답변"
            style_name = "User" if message["role"] == "user" else "Assistant"
            elements.append(Paragraph(f"{role_text}:", styles[style_name]))

            if message.get("stock_code") and message.get("stock_name"):
                elements.append(Paragraph(f"{message['stock_name']} ({message['stock_code']})", styles["Normal-KO"]))

            if message["role"] == "assistant" and message.get("components"):
                try:
                    logger.info(f"메시지 {message.get('id', '')}의 components를 사용하여 PDF 생성")
                    message_elements = self._convert_components_to_pdf_elements(message["components"], styles)
                    elements.extend(message_elements)
                except Exception as e:
                    logger.error(f"Components 변환 중 오류: {str(e)}, 기본 content로 처리")
                    self._add_markdown_content_to_elements(message, elements, styles, font_name, bold_font, expert_mode)
            else:
                self._add_markdown_content_to_elements(message, elements, styles, font_name, bold_font, expert_mode)

            elements.append(Spacer(1, 10))
            if idx > 0 and idx % 20 == 0:
                elements.append(PageBreak())
                elements.append(Paragraph(f"채팅 내용: {chat_session['title']} (계속)", styles["Title-KO"]))
                elements.append(Spacer(1, 12))

        doc.build(elements)
        buffer.seek(0)
        return buffer

    def _add_markdown_content_to_elements(self, message: Dict[str, Any], elements: List, styles, font_name: str, bold_font: str, expert_mode: bool):
        """메시지의 content를 마크다운으로 변환하여 elements에 추가합니다."""
        # 메시지 내용 - 모드에 따라 다른 내용 선택
        content = message["content"]
        if message["role"] == "assistant" and expert_mode and "content_expert" in message and message["content_expert"]:
            # 전문가 모드가 요청되었고, 전문가 모드 내용이 있는 경우만 사용
            content = message["content_expert"]

        # 차트 placeholder를 실제 차트 데이터로 대체
        if message["role"] == "assistant" and message.get("components"):
            content = replace_chart_placeholders_with_components(content, message["components"])
            logger.info(f"메시지 {message.get('id', '')}의 차트 placeholder 대체 완료")

        # 마크다운 변환 (strip_markdown 대신 convert_markdown 사용)
        markdown_elements = convert_markdown(content)

        # 변환된 마크다운 요소 추가
        for elem in markdown_elements:
            try:
                # 테이블 요소인 경우 ReportLab 테이블로 변환
                if "type" in elem and elem["type"] == "table":
                    # 테이블 데이터 가져오기
                    table_data = elem["data"]
                    if table_data and len(table_data) > 0:
                        # 열 너비 계산 (모든 열의 너비 동일하게 설정)
                        col_width = 450 / max(1, len(table_data[0]))  # A4 용지 너비에 맞게 조정
                        column_widths = [col_width] * len(table_data[0])

                        # 셀 데이터를 Paragraph로 변환하여 컬럼 너비에 맞춰 자동 줄바꿈(wrap) 처리
                        table_data_wrapped = []
                        for row_idx, row in enumerate(table_data):
                            wrapped_row = []
                            for col_idx, cell in enumerate(row):
                                # 헤더(첫 행)는 굵은 글씨, 나머지는 일반 스타일 적용
                                if row_idx == 0:
                                    wrapped_row.append(Paragraph(cell, styles["Heading5-KO"]))
                                else:
                                    wrapped_row.append(Paragraph(cell, styles["Normal-KO"]))  # 테이블 셀은 들여쓰기 없이 유지
                            table_data_wrapped.append(wrapped_row)
                        # ReportLab 테이블 생성 (셀 데이터는 모두 Paragraph)
                        table = Table(table_data_wrapped, colWidths=column_widths)
                        # 테이블 스타일 설정
                        table_style = [
                            ("FONTNAME", (0, 0), (-1, -1), font_name),
                            ("FONTSIZE", (0, 0), (-1, -1), 9),
                            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),  # 헤더 배경색
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                            ("TOPPADDING", (0, 0), (-1, -1), 4),
                        ]
                        table.setStyle(TableStyle(table_style))
                        elements.append(table)
                        elements.append(Spacer(1, 8))
                    continue

                # 일반 텍스트 요소 처리
                # <b> 태그를 굵은 폰트로 직접 변환
                text = elem["text"]
                # <b> 태그에 폰트 이름을 명시적으로 지정
                text = text.replace("<b>", f'<font face="{bold_font}">')
                text = text.replace("</b>", "</font>")

                elements.append(Paragraph(text, styles[elem["style"]]))

                # 단락 사이에 작은 간격 추가
                if elem["style"] not in ["Heading1-KO", "Heading2-KO", "Heading3-KO", "Heading4-KO", "Heading5-KO", "Heading6-KO"]:
                    elements.append(Spacer(1, 4))
            except Exception as e:
                logger.error(f"PDF 생성 중 오류 발생: {str(e)}, 내용: {elem['text'][:100] if 'text' in elem else str(elem)[:100]}...")
                # 오류 발생 시 일반 텍스트로 시도
                try:
                    if "text" in elem:
                        plain_text = re.sub(r"<[^>]+>", "", elem["text"])
                        elements.append(Paragraph(plain_text, styles["Paragraph-KO"]))  # 들여쓰기 적용된 스타일 사용
                        elements.append(Spacer(1, 4))
                except:
                    logger.error(f"일반 텍스트 변환도 실패: {str(elem)[:100]}...")
                    # 계속 진행
