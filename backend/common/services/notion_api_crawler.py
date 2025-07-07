"""노션 API를 사용한 크롤러"""

import re
import requests
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse, parse_qs

class NotionAPICrawler:
    """노션 API를 사용한 크롤러"""
    
    def __init__(self, notion_token: Optional[str] = None):
        """
        Args:
            notion_token: 노션 API 토큰 (선택사항)
        """
        self.notion_token = notion_token
        self.session = requests.Session()
        
        if notion_token:
            self.session.headers.update({
                'Authorization': f'Bearer {notion_token}',
                'Content-Type': 'application/json',
                'Notion-Version': '2022-06-28'
            })
    
    def extract_page_id_from_url(self, notion_url: str) -> Optional[str]:
        """노션 URL에서 페이지 ID를 추출합니다.
        
        Args:
            notion_url: 노션 페이지 URL
            
        Returns:
            페이지 ID 또는 None
        """
        try:
            # URL 파싱
            parsed_url = urlparse(notion_url)
            
            # 경로에서 페이지 ID 추출
            path = parsed_url.path
            
            # 일반적인 노션 URL 패턴들
            patterns = [
                r'/([a-f0-9]{32})',  # 32자리 hex
                r'/([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})',  # UUID 형태
                r'/([a-f0-9]{8}[a-f0-9]{4}[a-f0-9]{4}[a-f0-9]{4}[a-f0-9]{12})',  # UUID without hyphens
            ]
            
            for pattern in patterns:
                match = re.search(pattern, path)
                if match:
                    page_id = match.group(1)
                    # 하이픈 제거하고 32자리로 맞춤
                    page_id = page_id.replace('-', '')
                    if len(page_id) == 32:
                        # UUID 형태로 변환
                        formatted_id = f"{page_id[:8]}-{page_id[8:12]}-{page_id[12:16]}-{page_id[16:20]}-{page_id[20:]}"
                        return formatted_id
            
            return None
            
        except Exception as e:
            print(f"페이지 ID 추출 실패: {e}")
            return None
    
    def get_page_content_public(self, notion_url: str) -> Optional[str]:
        """공개 노션 페이지의 콘텐츠를 가져옵니다 (API 토큰 불필요).
        
        Args:
            notion_url: 노션 페이지 URL
            
        Returns:
            추출된 텍스트 콘텐츠 또는 None
        """
        try:
            print(f"🔍 공개 노션 페이지 콘텐츠 추출 시도: {notion_url}")
            
            # 공개 페이지에서 메타데이터 추출을 시도
            response = self.session.get(notion_url, timeout=10)
            
            if response.status_code == 200:
                html_content = response.text
                
                # 기본적인 텍스트 추출
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(html_content, 'html.parser')
                
                extracted_text = []
                
                # 1. 다양한 메타 태그 추출
                meta_tags = [
                    ('og:title', '제목'),
                    ('og:description', '설명'),
                    ('description', '페이지 설명'),
                    ('twitter:title', '트위터 제목'),
                    ('twitter:description', '트위터 설명'),
                    ('apple-mobile-web-app-title', '앱 제목')
                ]
                
                for property_name, label in meta_tags:
                    meta = soup.find('meta', property=property_name) or soup.find('meta', attrs={'name': property_name})
                    if meta and meta.get('content'):
                        content = meta['content'].strip()
                        if content and content not in [item.split(': ', 1)[-1] for item in extracted_text]:
                            extracted_text.append(f"{label}: {content}")
                
                # 2. 제목 태그 추출
                title_tag = soup.find('title')
                if title_tag:
                    title_text = title_tag.get_text().strip()
                    if title_text and "Notion" not in title_text and title_text not in [item.split(': ', 1)[-1] for item in extracted_text]:
                        extracted_text.append(f"페이지 제목: {title_text}")
                
                # 3. JSON-LD 구조화 데이터 추출
                json_ld_scripts = soup.find_all('script', type='application/ld+json')
                for script in json_ld_scripts:
                    try:
                        import json
                        data = json.loads(script.string)
                        if isinstance(data, dict):
                            if 'name' in data:
                                extracted_text.append(f"구조화 데이터 이름: {data['name']}")
                            if 'description' in data:
                                extracted_text.append(f"구조화 데이터 설명: {data['description']}")
                            if 'headline' in data:
                                extracted_text.append(f"헤드라인: {data['headline']}")
                    except:
                        continue
                
                # 4. 노션 특화 데이터 추출 시도
                # 노션 페이지의 초기 상태 데이터를 찾아보기
                scripts = soup.find_all('script')
                for script in scripts:
                    if script.string and ('window.__INITIAL_STATE__' in script.string or 'window.__NEXT_DATA__' in script.string):
                        script_content = script.string
                        
                        # 간단한 패턴 매칭으로 제목이나 텍스트 추출 시도
                        import re
                        
                        # 한글 텍스트 패턴 찾기
                        korean_patterns = [
                            r'"title":\s*"([^"]*[가-힣][^"]*)"',
                            r'"name":\s*"([^"]*[가-힣][^"]*)"',
                            r'"text":\s*"([^"]*[가-힣][^"]*)"',
                            r'"content":\s*"([^"]*[가-힣][^"]*)"'
                        ]
                        
                        for pattern in korean_patterns:
                            matches = re.findall(pattern, script_content)
                            for match in matches[:5]:  # 상위 5개만
                                if len(match) > 2 and match not in [item.split(': ', 1)[-1] for item in extracted_text]:
                                    extracted_text.append(f"스크립트 데이터: {match}")
                        
                        break
                
                # 5. 기본 텍스트 노드에서 의미있는 텍스트 찾기
                text_elements = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'span', 'div'])
                for element in text_elements[:20]:  # 상위 20개만 확인
                    text = element.get_text().strip()
                    if text and len(text) > 5 and len(text) < 200:  # 적절한 길이의 텍스트
                        # 한글이 포함된 텍스트 우선
                        if re.search(r'[가-힣]', text) and text not in [item.split(': ', 1)[-1] for item in extracted_text]:
                            extracted_text.append(f"페이지 텍스트: {text}")
                            if len(extracted_text) > 10:  # 너무 많으면 중단
                                break
                
                if extracted_text:
                    result = '\n'.join(extracted_text)
                    print(f"✅ 공개 페이지에서 확장된 정보 추출: {len(result)} 문자")
                    print(f"추출된 항목 수: {len(extracted_text)}개")
                    return result
                else:
                    print("❌ 공개 페이지에서 콘텐츠를 추출할 수 없습니다")
                    return None
            else:
                print(f"❌ 페이지 접근 실패: HTTP {response.status_code}")
                return None
                
        except Exception as e:
            print(f"❌ 공개 페이지 크롤링 중 오류: {e}")
            return None
    
    def get_page_content_with_api(self, page_id: str) -> Optional[str]:
        """노션 API를 사용하여 페이지 콘텐츠를 가져옵니다.
        
        Args:
            page_id: 노션 페이지 ID
            
        Returns:
            추출된 텍스트 콘텐츠 또는 None
        """
        if not self.notion_token:
            print("❌ 노션 API 토큰이 없습니다")
            return None
        
        try:
            print(f"🔍 노션 API로 페이지 조회: {page_id}")
            
            # 페이지 정보 가져오기
            page_url = f"https://api.notion.com/v1/pages/{page_id}"
            page_response = self.session.get(page_url)
            
            if page_response.status_code != 200:
                print(f"❌ 페이지 조회 실패: {page_response.status_code}")
                return None
            
            page_data = page_response.json()
            
            # 블록 콘텐츠 가져오기
            blocks_url = f"https://api.notion.com/v1/blocks/{page_id}/children"
            blocks_response = self.session.get(blocks_url)
            
            if blocks_response.status_code != 200:
                print(f"❌ 블록 조회 실패: {blocks_response.status_code}")
                return None
            
            blocks_data = blocks_response.json()
            
            # 텍스트 추출
            extracted_texts = []
            
            # 페이지 제목 추출
            if 'properties' in page_data:
                title_prop = page_data['properties'].get('title') or page_data['properties'].get('Name')
                if title_prop and 'title' in title_prop:
                    title_texts = [item.get('text', {}).get('content', '') for item in title_prop['title']]
                    if title_texts:
                        extracted_texts.append(f"제목: {''.join(title_texts)}")
            
            # 블록 콘텐츠 추출
            for block in blocks_data.get('results', []):
                text = self._extract_text_from_block(block)
                if text:
                    extracted_texts.append(text)
            
            if extracted_texts:
                result = '\n'.join(extracted_texts)
                print(f"✅ 노션 API로 콘텐츠 추출 성공: {len(result)} 문자")
                return result
            else:
                print("❌ 추출된 콘텐츠가 없습니다")
                return None
                
        except Exception as e:
            print(f"❌ 노션 API 크롤링 중 오류: {e}")
            return None
    
    def _extract_text_from_block(self, block: Dict[str, Any]) -> Optional[str]:
        """노션 블록에서 텍스트를 추출합니다."""
        try:
            block_type = block.get('type')
            
            if not block_type:
                return None
            
            block_data = block.get(block_type, {})
            
            # 텍스트가 있는 블록 타입들
            text_types = ['paragraph', 'heading_1', 'heading_2', 'heading_3', 
                         'bulleted_list_item', 'numbered_list_item', 'quote', 'callout']
            
            if block_type in text_types:
                rich_text = block_data.get('rich_text', [])
                if rich_text:
                    texts = [item.get('text', {}).get('content', '') for item in rich_text]
                    return ''.join(texts)
            
            return None
            
        except Exception:
            return None
    
    async def crawl_notion_page(self, notion_url: str) -> Optional[str]:
        """노션 페이지를 크롤링합니다.
        
        Args:
            notion_url: 노션 페이지 URL
            
        Returns:
            추출된 텍스트 콘텐츠 또는 None
        """
        try:
            print(f"🔍 노션 API 크롤러로 페이지 분석: {notion_url}")
            
            # 1순위: 공개 페이지에서 기본 정보 추출 시도
            public_content = self.get_page_content_public(notion_url)
            if public_content:
                return public_content
            
            # 2순위: API 토큰이 있으면 API 사용
            if self.notion_token:
                page_id = self.extract_page_id_from_url(notion_url)
                if page_id:
                    api_content = self.get_page_content_with_api(page_id)
                    if api_content:
                        return api_content
            
            # 3순위: 최소한의 정보라도 제공
            print("⚠️ 노션 페이지 콘텐츠 추출 실패, 기본 정보 제공")
            
            # URL에서 페이지 ID 추출하여 기본 정보 생성
            page_id = self.extract_page_id_from_url(notion_url)
            
            fallback_info = []
            fallback_info.append(f"노션 페이지 링크: {notion_url}")
            
            if page_id:
                fallback_info.append(f"페이지 ID: {page_id}")
            
            # URL 구조 분석
            if 'notion.site' in notion_url:
                fallback_info.append("유형: 노션 공개 사이트")
            elif 'notion.so' in notion_url:
                fallback_info.append("유형: 노션 워크스페이스")
            
            fallback_info.append("상태: JavaScript 렌더링 필요 - 브라우저에서 직접 확인 필요")
            fallback_info.append("참고: 실제 콘텐츠는 노션 앱이나 브라우저에서 확인하세요")
            
            result = '\n'.join(fallback_info)
            print(f"✅ 기본 정보 제공: {len(result)} 문자")
            return result
            
        except Exception as e:
            print(f"❌ 노션 크롤링 중 오류: {e}")
            return None

# 테스트 함수
async def test_notion_api_crawler():
    """노션 API 크롤러 테스트"""
    crawler = NotionAPICrawler()
    
    # https://sequoia-ray-2fa.notion.site/1f732f6a257980a0a95ad7126bc0e46e?pvs=4
    test_url = "https://sequoia-ray-2fa.notion.site/1f732f6a257980a0a95ad7126bc0e46e?pvs=4"

    result = await crawler.crawl_notion_page(test_url)
    
    if result:
        print(f"크롤링 결과:\n{result}")
    else:
        print("크롤링 실패")

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_notion_api_crawler()) 