"""
PDF 생성 서비스

이 모듈은 채팅 세션의 메시지를 PDF로 변환하는 기능을 제공합니다.
"""
import os
import io
import uuid
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any
from pathlib import Path
import re

from loguru import logger
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from google.cloud import storage
from markdown_it import MarkdownIt
import xml.etree.ElementTree as ET

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
    md.enable('table')  # 테이블 지원 활성화
    
    # 마크다운을 HTML로 변환
    html = md.render(text)
    
    # 변환된 HTML을 로그로 출력(디버깅용)
    #print("==== 변환된 HTML ====")
    #print(html)
    
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
    lines = html_content.split('\n')
    current_block = []
    current_style = 'Normal-KO'
    
    for line in lines:
        # 빈 줄 건너뛰기
        if not line.strip():
            if current_block:
                result.append({
                    'text': ''.join(current_block),
                    'style': current_style
                })
                current_block = []
                current_style = 'Normal-KO'
            continue
        
        # 헤더 태그 확인
        if re.search(r'<h([1-6])[^>]*>(.*?)</h\1>', line):
            # 이전 블록이 있으면 추가
            if current_block:
                result.append({
                    'text': ''.join(current_block),
                    'style': current_style
                })
                current_block = []
            
            # 헤더 수준 추출
            header_match = re.search(r'<h([1-6])[^>]*>(.*?)</h\1>', line)
            if header_match:
                level = header_match.group(1)
                content = header_match.group(2)
                result.append({
                    'text': content,
                    'style': f'Heading{level}-KO'
                })
            continue
        
        # 목록 항목 확인
        if '<li>' in line:
            # <li> 태그를 추출하여 처리
            li_content = re.sub(r'<li[^>]*>(.*?)</li>', r'• \1', line)
            current_block.append(li_content)
            current_style = 'ListItem-KO'
            continue
        
        # 코드 블록 확인
        if '<pre>' in line or '<code>' in line:
            # 이전 블록이 있으면 추가
            if current_block:
                result.append({
                    'text': ''.join(current_block),
                    'style': current_style
                })
                current_block = []
            
            # 코드 컨텐츠 추출
            code_content = re.sub(r'<pre[^>]*><code[^>]*>(.*?)</code></pre>', r'\1', line)
            code_content = re.sub(r'<code[^>]*>(.*?)</code>', r'\1', code_content)
            
            result.append({
                'text': code_content,
                'style': 'Code-KO'
            })
            continue
        
        # 인용구 확인
        if '<blockquote>' in line:
            quote_content = re.sub(r'<blockquote[^>]*>(.*?)</blockquote>', r'\1', line)
            current_block.append(quote_content)
            current_style = 'Quote-KO'
            continue
        
        # 일반 텍스트 (다른 특별한 태그가 없는 경우)
        current_block.append(line)
    
    # 마지막 블록 처리
    if current_block:
        result.append({
            'text': ''.join(current_block),
            'style': current_style
        })
    
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
    table_pattern = re.compile(r'<table>(.*?)</table>', re.DOTALL)
    table_matches = table_pattern.findall(html_content)
    
    for table_html in table_matches:
        # 행 추출
        rows = []
        row_pattern = re.compile(r'<tr>(.*?)</tr>', re.DOTALL)
        row_matches = row_pattern.findall(table_html)
        
        for row_html in row_matches:
            # 헤더 셀 추출
            cell_pattern = re.compile(r'<t[hd]>(.*?)</t[hd]>', re.DOTALL)
            cell_matches = cell_pattern.findall(row_html)
            
            # 각 셀의 HTML 태그 제거
            row = []
            for cell_html in cell_matches:
                # HTML 태그 제거
                cell_text = re.sub(r'<[^>]+>', '', cell_html).strip()
                row.append(cell_text)
            
            if row:  # 비어있지 않은 행만 추가
                rows.append(row)
        
        if rows:  # 비어있지 않은 테이블만 추가
            tables.append({
                'data': rows,
                'type': 'table'
            })
    
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
            table_html = re.search(r'(<table>.*?</table>)', html, re.DOTALL)
            if table_html:
                html = html.replace(table_html.group(1), placeholder, 1)
                table_placeholders[placeholder] = table
        
        # HTML을 단락으로 분리해 ReportLab 형식으로 변환
        result = []
        
        # 단락 분리를 위해 p 태그로 구분
        paragraphs = re.split(r'(<\/?(?:p|h[1-6]|ul|ol|li|pre|blockquote)[^>]*>)', html)
        buffer = []
        current_style = 'Normal-KO'
        
        for part in paragraphs:
            if not part.strip():
                continue
            
            # 테이블 플레이스홀더 확인
            table_match = None
            for placeholder in table_placeholders:
                if placeholder in part:
                    # 이전 내용이 있으면 먼저 처리
                    if buffer:
                        result.append({'text': ''.join(buffer), 'style': current_style})
                        buffer = []
                    
                    # 테이블 데이터 추가
                    result.append(table_placeholders[placeholder])
                    
                    # 플레이스홀더를 제거한 나머지 부분 처리
                    remaining = part.replace(placeholder, '')
                    if remaining.strip():
                        buffer.append(remaining)
                    
                    table_match = True
                    break
            
            if table_match:
                continue
                
            # 헤더 태그 확인 - 스타일 설정 용도
            if re.match(r'<h1[^>]*>', part):
                if buffer:
                    result.append({'text': ''.join(buffer), 'style': current_style})
                    buffer = []
                current_style = 'Heading1-KO'
            elif re.match(r'<h2[^>]*>', part):
                if buffer:
                    result.append({'text': ''.join(buffer), 'style': current_style})
                    buffer = []
                current_style = 'Heading2-KO'
            elif re.match(r'<h3[^>]*>', part):
                if buffer:
                    result.append({'text': ''.join(buffer), 'style': current_style})
                    buffer = []
                current_style = 'Heading3-KO'
            elif re.match(r'<h4[^>]*>', part):
                if buffer:
                    result.append({'text': ''.join(buffer), 'style': current_style})
                    buffer = []
                current_style = 'Heading4-KO'
            elif re.match(r'<h5[^>]*>', part):
                if buffer:
                    result.append({'text': ''.join(buffer), 'style': current_style})
                    buffer = []
                current_style = 'Heading5-KO'
            elif re.match(r'<h6[^>]*>', part):
                if buffer:
                    result.append({'text': ''.join(buffer), 'style': current_style})
                    buffer = []
                current_style = 'Heading6-KO'
            elif re.match(r'<li[^>]*>', part) or re.match(r'<ul[^>]*>', part) or re.match(r'<ol[^>]*>', part):
                if buffer and current_style != 'ListItem-KO':
                    result.append({'text': ''.join(buffer), 'style': current_style})
                    buffer = []
                current_style = 'ListItem-KO'
            elif re.match(r'<pre[^>]*>', part) or re.match(r'<code[^>]*>', part):
                if buffer:
                    result.append({'text': ''.join(buffer), 'style': current_style})
                    buffer = []
                current_style = 'Code-KO'
            elif re.match(r'<blockquote[^>]*>', part):
                if buffer:
                    result.append({'text': ''.join(buffer), 'style': current_style})
                    buffer = []
                current_style = 'Quote-KO'
            
            # 닫는 태그는 버퍼에 추가하지 않음
            if not part.startswith('</'):
                buffer.append(part)
            
            # 닫는 태그를 만나면 현재 내용을 결과에 추가하고 스타일 초기화
            if part.startswith('</h') or part == '</p>' or part == '</li>' or part == '</pre>' or part == '</blockquote>':
                if buffer:
                    result.append({'text': ''.join(buffer), 'style': current_style})
                    buffer = []
                current_style = 'Normal-KO'
        
        # 남은 내용 처리
        if buffer:
            result.append({'text': ''.join(buffer), 'style': current_style})
        
        # 결과가 없으면 원본 HTML을 기본 스타일로 한 번에 반환
        if not result:
            result.append({'text': html, 'style': 'Normal-KO'})
        
        return result
    except Exception as e:
        logger.error(f"마크다운 변환 중 오류 발생: {str(e)}")
        # 오류 발생 시 원본 텍스트를 기본 스타일로 반환
        return [{'text': text, 'style': 'Normal-KO'}]

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
            
            if 'NanumGothic' not in registered_fonts:
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
                        pdfmetrics.registerFont(TTFont('NanumGothic', str(nanum_regular_path)))
                        pdfmetrics.registerFont(TTFont('NanumGothicBold', str(nanum_bold_path)))
                        logger.info("나눔고딕 폰트 등록 완료")
        except Exception as e:
            logger.warning(f"폰트 등록 중 오류 발생: {str(e)}")
    
    async def generate_chat_pdf(
        self, 
        chat_session: Dict[str, Any], 
        messages: List[Dict[str, Any]],
        user_id: str,
        expert_mode: bool = False  # 전문가 모드 여부 매개변수 추가
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
            expert_mode  # 전문가 모드 여부 전달
        )
        
        # 파일명 설정 - 세션 ID 대신 종목명(종목코드) 사용
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_id = chat_session["id"]
        
        # 채팅 세션에서 종목 정보 확인
        stock_info = ""
        if chat_session.get('title'):
            stock_info = chat_session['title']
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
        
        return {
            "file_name": file_name,
            "download_url": download_url,
            "expires_at": expires_at
        }
    
    def _create_pdf_from_messages(
        self, 
        chat_session: Dict[str, Any], 
        messages: List[Dict[str, Any]],
        expert_mode: bool = False  # 전문가 모드 여부 매개변수 추가
    ) -> io.BytesIO:
        """
        메시지 목록을 PDF로 변환합니다.
        
        Args:
            chat_session: 채팅 세션 정보
            messages: 메시지 목록
            expert_mode: 전문가 모드 사용 여부 (True: 전문가 모드, False: 주린이 모드)
            
        Returns:
            PDF 문서가 담긴 BytesIO 객체
        """
        # PDF 문서 생성을 위한 버퍼
        buffer = io.BytesIO()
        
        # 문서 스타일 설정
        styles = getSampleStyleSheet()
        
        # 한글 지원 스타일 추가
        font_name = 'NanumGothic' if 'NanumGothic' in pdfmetrics.getRegisteredFontNames() else 'Helvetica'
        bold_font = 'NanumGothicBold' if 'NanumGothicBold' in pdfmetrics.getRegisteredFontNames() else 'Helvetica-Bold'
        
        # 이미 'Title' 스타일이 존재하므로 재정의하는 대신 사용
        # 기존 'Title' 스타일을 복제하고 폰트만 한글 폰트로 변경
        title_style = styles['Title']
        title_style.fontName = bold_font
        
        # 기본 스타일
        styles.add(ParagraphStyle(
            name='Normal-KO',
            fontName=font_name,
            fontSize=10,
            leading=14
        ))
        
        # 헤딩 스타일 (h1 ~ h6)
        styles.add(ParagraphStyle(
            name='Heading1-KO',
            fontName=bold_font,
            fontSize=16,
            leading=20,
            spaceBefore=12,
            spaceAfter=6
        ))
        
        styles.add(ParagraphStyle(
            name='Heading2-KO',
            fontName=bold_font,
            fontSize=14,
            leading=18,
            spaceBefore=10,
            spaceAfter=6
        ))
        
        styles.add(ParagraphStyle(
            name='Heading3-KO',
            fontName=bold_font,
            fontSize=12,
            leading=16,
            spaceBefore=8,
            spaceAfter=6
        ))
        
        styles.add(ParagraphStyle(
            name='Heading4-KO',
            fontName=bold_font,
            fontSize=11,
            leading=15,
            spaceBefore=6,
            spaceAfter=4
        ))
        
        styles.add(ParagraphStyle(
            name='Heading5-KO',
            fontName=bold_font,
            fontSize=10,
            leading=14,
            spaceBefore=5,
            spaceAfter=3
        ))
        
        styles.add(ParagraphStyle(
            name='Heading6-KO',
            fontName=bold_font,
            fontSize=10,
            leading=14,
            spaceBefore=5,
            spaceAfter=3,
            textColor=colors.gray
        ))
        
        # 인용구 스타일
        styles.add(ParagraphStyle(
            name='Quote-KO',
            fontName=font_name,
            fontSize=10,
            leading=14,
            leftIndent=20,
            rightIndent=20,
            spaceAfter=6,
            textColor=colors.darkgray,
            borderColor=colors.lightgrey,
            borderWidth=1,
            borderPadding=5,
            borderRadius=2
        ))
        
        # 코드 스타일
        styles.add(ParagraphStyle(
            name='Code-KO',
            fontName='Courier',
            fontSize=9,
            leading=11,
            backColor=colors.lightgrey,
            borderColor=colors.grey,
            borderWidth=0.5,
            borderPadding=4,
            borderRadius=2,
            spaceBefore=4,
            spaceAfter=6
        ))
        
        # 목록 항목 스타일
        styles.add(ParagraphStyle(
            name='ListItem-KO',
            fontName=font_name,
            fontSize=10,
            leading=14,
            leftIndent=10
        ))
        
        # 메시지 작성자 스타일
        styles.add(ParagraphStyle(
            name='User',
            fontName=bold_font,
            fontSize=10,
            leading=14,
            textColor=colors.blue
        ))
        
        styles.add(ParagraphStyle(
            name='Assistant',
            fontName=bold_font,
            fontSize=10,
            leading=14,
            textColor=colors.green
        ))
        
        # 볼드 텍스트용 스타일 추가
        styles.add(ParagraphStyle(
            name='Bold-KO',
            fontName=bold_font,
            fontSize=10,
            leading=14
        ))
        
        # XML 태그를 허용하도록 설정 - HTML 태그 추가
        allowedTags = [
            'b', 'i', 'u', 'strong', 'em', 'strike', 'font', 'code', 'pre', 'a', 'link', 'br',
            'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol', 'li', 'blockquote', 'span',
            'table', 'tr', 'th', 'td', 'thead', 'tbody', 'tfoot'
        ]
        
        for style in styles.byName.values():
            if not hasattr(style, 'allowedTags'):
                style.allowedTags = allowedTags
            else:
                # 기존 allowedTags가 있으면 내용 추가
                for tag in allowedTags:
                    if tag not in style.allowedTags:
                        style.allowedTags.append(tag)
        
        # bold 태그 처리를 위한 추가 설정
        # ReportLab에서 strong 및 b 태그를 굵은 글꼴로 처리하도록 설정
        for style in styles.byName.values():
            if hasattr(style, 'fontName'):
                # 기본 스타일은 Normal-KO이므로 굵은 폰트는 NanumGothicBold 사용
                if not hasattr(style, 'bold_name'):
                    style.bold_name = bold_font
        
        # PDF 문서 생성
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            title=chat_session["title"],
            author="인텔리오 AI ",
            subject="채팅 내용",
            creator="인텔리오 AI"
        )
        
        # 문서 내용 구성
        elements = []

        # ===== [회사 정보 헤더] =====
        # PDF 모든 문서 최상단에 회사 정보 고정 삽입
        # ===== [회사 정보 헤더: 3줄 모두 동일 자간(leading) 적용] =====
        # 자간(leading)은 두 번째 줄(부제목) 스타일의 14로 통일
        COMMON_LEADING = 14
        # 1. 메인 제목: 스탁이지 : StockEasy (좌측 정렬, 글자 크기 30% 축소, 동일 자간)
        from reportlab.lib.enums import TA_LEFT
        title_left_style = ParagraphStyle(
            name="Title-Left-KO",
            parent=styles["Title"],
            fontName=bold_font,
            fontSize=int(styles["Title"].fontSize * 0.7),  # 약 30% 축소
            alignment=TA_LEFT,
            leading=COMMON_LEADING,
            spaceAfter=2
        )
        elements.append(Paragraph("스탁이지 : StockEasy", title_left_style))
        # 2. 부제목: 금융 데이터 기반 AI 분석 에이전트 (작게, 동일 자간)
        subtitle_style = ParagraphStyle(
            name="SubTitle-KO",
            fontName=font_name,
            fontSize=11,
            leading=COMMON_LEADING,
            alignment=TA_LEFT,
            spaceAfter=2
        )
        elements.append(Paragraph("금융 데이터 기반 AI 분석 에이전트", subtitle_style))
        # 3. 회사명/URL: (주)인텔리오 https://www.intellio.kr (더 작게, 동일 자간)
        company_style = ParagraphStyle(
            name="Company-KO",
            fontName=font_name,
            fontSize=9,
            leading=COMMON_LEADING,
            alignment=TA_LEFT,
            textColor=colors.gray,
            spaceAfter=4
        )
        elements.append(Paragraph("(주)인텔리오 https://www.intellio.kr", company_style))
        # 4. 구분선
        from reportlab.platypus import HRFlowable
        elements.append(HRFlowable(width="100%", thickness=0.7, color=colors.grey, spaceBefore=4, spaceAfter=8))
        # 구분선 아래에 본문(채팅 제목)과의 충분한 여백 추가
        elements.append(Spacer(1, 24))  # 기존보다 넉넉한 여백
        # ===== [원래 제목 및 본문] =====
        # 기존 채팅 세션 제목 추가(회사 정보 헤더 아래)
        elements.append(Paragraph(f"{chat_session['title']}", styles["Title"]))
        elements.append(Spacer(1, 12))
        # 메시지 목록 추가
        elements.append(Paragraph("", styles["Heading1-KO"]))
        elements.append(Spacer(1, 10))
        
        # 메시지 순서대로 처리
        for idx, message in enumerate(messages):
            if message["role"] == "status":
                # 상태 메시지는 처리하지 않음
                continue
            
            # 메시지 작성자 표시
            role_text = "질문" if message["role"] == "user" else "답변"
            style_name = "User" if message["role"] == "user" else "Assistant"
            
            elements.append(Paragraph(f"{role_text}:", styles[style_name]))
            
            # 종목 정보가 있으면 표시
            if message.get("stock_code") and message.get("stock_name"):
                elements.append(
                    Paragraph(
                        f"{message['stock_name']} ({message['stock_code']})", 
                        styles["Normal-KO"]
                    )
                )
            
            # 메시지 내용 - 모드에 따라 다른 내용 선택
            content = message["content"]
            if message["role"] == "assistant" and expert_mode and "content_expert" in message and message["content_expert"]:
                # 전문가 모드가 요청되었고, 전문가 모드 내용이 있는 경우만 사용
                content = message["content_expert"]
            # 전문가 모드가 아니거나 전문가 내용이 없는 경우 기본 content 사용
            
            # 마크다운 변환 (strip_markdown 대신 convert_markdown 사용)
            markdown_elements = convert_markdown(content)
            
            # 변환된 마크다운 요소 추가
            for elem in markdown_elements:
                try:
                    # 테이블 요소인 경우 ReportLab 테이블로 변환
                    if 'type' in elem and elem['type'] == 'table':
                        # 테이블 데이터 가져오기
                        table_data = elem['data']
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
                                        wrapped_row.append(Paragraph(cell, styles['Heading5-KO']))
                                    else:
                                        wrapped_row.append(Paragraph(cell, styles['Normal-KO']))
                                table_data_wrapped.append(wrapped_row)
                            # ReportLab 테이블 생성 (셀 데이터는 모두 Paragraph)
                            table = Table(table_data_wrapped, colWidths=column_widths)
                            # 테이블 스타일 설정
                            table_style = [
                                ('FONTNAME', (0, 0), (-1, -1), font_name),
                                ('FONTSIZE', (0, 0), (-1, -1), 9),
                                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),  # 헤더 배경색
                                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                                ('TOPPADDING', (0, 0), (-1, -1), 4),
                            ]
                            table.setStyle(TableStyle(table_style))
                            elements.append(table)
                            elements.append(Spacer(1, 8))
                        continue
                    
                    # 일반 텍스트 요소 처리
                    # <b> 태그를 굵은 폰트로 직접 변환
                    text = elem['text']
                    # <b> 태그에 폰트 이름을 명시적으로 지정
                    text = text.replace("<b>", f'<font face="{bold_font}">')
                    text = text.replace("</b>", "</font>")
                    
                    elements.append(Paragraph(text, styles[elem['style']]))
                    
                    # 단락 사이에 작은 간격 추가
                    if elem['style'] not in ['Heading1-KO', 'Heading2-KO', 'Heading3-KO', 'Heading4-KO', 'Heading5-KO', 'Heading6-KO']:
                        elements.append(Spacer(1, 4))
                except Exception as e:
                    logger.error(f"PDF 생성 중 오류 발생: {str(e)}, 내용: {elem['text'][:100] if 'text' in elem else str(elem)[:100]}...")
                    # 오류 발생 시 일반 텍스트로 시도
                    try:
                        if 'text' in elem:
                            plain_text = re.sub(r'<[^>]+>', '', elem['text'])
                            elements.append(Paragraph(plain_text, styles['Normal-KO']))
                            elements.append(Spacer(1, 4))
                    except:
                        logger.error(f"일반 텍스트 변환도 실패: {str(elem)[:100]}...")
                        # 계속 진행
            
            # 메시지 구분선 추가
            elements.append(Spacer(1, 10))
            
            # 20개 메시지마다 페이지 나누기
            if idx > 0 and idx % 20 == 0:
                elements.append(PageBreak())
                elements.append(Paragraph(f"채팅 내용: {chat_session['title']} (계속)", styles["Title"]))
                elements.append(Spacer(1, 12))
        
        # PDF 생성
        doc.build(elements)
        
        buffer.seek(0)
        return buffer
    
    async def _upload_to_gcs(self, file_path: Path, gcs_path: str) -> str:
        """
        파일을 Google Cloud Storage에 업로드하고 서명된 URL을 반환합니다.
        
        Args:
            file_path: 로컬 파일 경로
            gcs_path: GCS 경로
            
        Returns:
            서명된 다운로드 URL
        """
        try:
            # GCS 클라이언트 초기화
            storage_client = storage.Client()
            bucket = storage_client.bucket(settings.GCS_BUCKET_NAME)
            
            # 파일 업로드
            blob = bucket.blob(gcs_path)
            with open(file_path, "rb") as f:
                blob.upload_from_file(f)
            
            logger.info(f"파일 업로드 완료: gs://{settings.GCS_BUCKET_NAME}/{gcs_path}")
            
            # 서명된 URL 생성 (24시간 유효)
            loop = asyncio.get_event_loop()
            url = await loop.run_in_executor(
                None,
                lambda: blob.generate_signed_url(
                    version="v4",
                    expiration=timedelta(hours=24),
                    method="GET"
                )
            )
            
            return url
            
        except Exception as e:
            logger.error(f"GCS 업로드 중 오류 발생: {str(e)}")
            # 로컬 개발 환경 또는 GCS 업로드 실패 시 로컬 파일 경로 생성
            # 임시 디렉토리 URL 생성 (실제 서버에서는 작동하지 않을 수 있음)
            try:
                # 임시 디렉토리에 파일 복사
                temp_dir = Path(settings.TEMP_DIR)
                if not temp_dir.exists():
                    temp_dir.mkdir(parents=True, exist_ok=True)
                
                file_name = os.path.basename(file_path)
                # 임시 디렉토리에 파일이 이미 있는 경우에는 복사하지 않음
                if file_path != temp_dir / file_name:
                    import shutil
                    shutil.copy2(file_path, temp_dir / file_name)
                
                # 개발 환경에서는 FastAPI 서버 URL을 반환
                base_url = settings.API_BASE_URL or "http://localhost:8000"
                local_url = f"{base_url}/temp/{file_name}"
                logger.warning(f"GCS 업로드 실패, 로컬 URL 반환: {local_url}")
                return local_url
            except Exception as copy_error:
                logger.error(f"로컬 파일 처리 중 오류 발생: {str(copy_error)}")
                # 최후의 수단으로 파일 경로 문자열 반환
                return f"file://{file_path}" 