"""경량 노션 크롤러 - Playwright 사용"""

import asyncio
import re
from typing import Optional

try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    print("⚠️ Playwright가 설치되지 않았습니다.")
    print("설치 명령어: pip install playwright && playwright install chromium")

class LightNotionCrawler:
    """경량 노션 크롤러 - Playwright 사용"""
    
    def __init__(self):
        self.timeout = 30000  # 30초 타임아웃
    
    async def crawl_notion_page(self, url: str) -> Optional[str]:
        """노션 페이지를 크롤링하여 텍스트 콘텐츠를 추출합니다.
        
        Args:
            url (str): 크롤링할 노션 URL
            
        Returns:
            Optional[str]: 추출된 텍스트 콘텐츠 또는 None
        """
        if not PLAYWRIGHT_AVAILABLE:
            print("❌ Playwright가 설치되지 않았습니다.")
            return None
        
        try:
            print(f"🔍 Playwright로 노션 크롤링 시작: {url}")
            
            async with async_playwright() as p:
                # Chromium 브라우저 실행 (경량)
                browser = await p.chromium.launch(
                    headless=True,
                    args=[
                        '--no-sandbox',
                        '--disable-dev-shm-usage',
                        '--disable-gpu',
                        '--disable-web-security',
                        '--disable-setuid-sandbox',
                        '--disable-dev-tools'
                    ]
                )
                
                page = await browser.new_page()
                
                # User-Agent 설정
                await page.set_extra_http_headers({
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                })
                
                # 페이지 로드
                await page.goto(url, wait_until='networkidle', timeout=self.timeout)
                
                # 페이지가 완전히 로드될 때까지 잠시 대기
                await page.wait_for_timeout(3000)
                
                # 노션 콘텐츠 영역을 찾기 위한 선택자들
                content_selectors = [
                    '[data-block-id]',  # 노션 블록
                    '.notion-page-content',
                    '.notion-page-block',
                    '[role="main"]',
                    'main',
                    'article'
                ]
                
                extracted_texts = []
                
                # 각 선택자로 콘텐츠 찾기
                for selector in content_selectors:
                    try:
                        elements = await page.query_selector_all(selector)
                        if elements:
                            print(f"✅ 발견된 요소 ({selector}): {len(elements)}개")
                            
                            for element in elements[:20]:  # 상위 20개만 처리
                                try:
                                    text = await element.inner_text()
                                    if text and len(text.strip()) > 10:  # 의미있는 텍스트만
                                        extracted_texts.append(text.strip())
                                except Exception:
                                    continue
                            
                            if extracted_texts:
                                break  # 콘텐츠를 찾았으면 다른 선택자는 시도하지 않음
                                
                    except Exception as e:
                        print(f"⚠️ 선택자 {selector} 처리 중 오류: {e}")
                        continue
                
                # 브라우저 종료
                await browser.close()
                
                if extracted_texts:
                    # 텍스트들을 결합
                    final_text = '\n\n'.join(extracted_texts)
                    
                    # 중복 제거 및 정리
                    lines = []
                    seen = set()
                    for line in final_text.split('\n'):
                        clean_line = line.strip()
                        if clean_line and len(clean_line) > 5 and clean_line not in seen:
                            lines.append(clean_line)
                            seen.add(clean_line)
                    
                    result = '\n'.join(lines)
                    print(f"✅ 노션 크롤링 성공: {len(result)} 문자 추출")
                    return result
                else:
                    print("❌ 노션 콘텐츠를 찾을 수 없습니다")
                    return None
                    
        except Exception as e:
            print(f"❌ 노션 크롤링 중 오류 발생: {str(e)}")
            return None

# 테스트 함수
async def test_playwright_crawler():
    """Playwright 크롤러 테스트"""
    crawler = LightNotionCrawler()
    
    test_url = "https://sequoia-ray-2fa.notion.site/1f732f6a257980a0a95ad7126bc0e46e?pvs=4"
    result = await crawler.crawl_notion_page(test_url)
    
    if result:
        print(f"크롤링 결과 (처음 500자):\n{result[:500]}")
    else:
        print("크롤링 실패")

if __name__ == "__main__":
    asyncio.run(test_playwright_crawler()) 