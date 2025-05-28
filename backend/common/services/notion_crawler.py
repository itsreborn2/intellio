
import requests
from bs4 import BeautifulSoup
import time
import json
from urllib.parse import urljoin
import re

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, WebDriverException
    from webdriver_manager.chrome import ChromeDriverManager
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    print("⚠️ Selenium이 설치되지 않았습니다. 동적 콘텐츠 크롤링을 위해 설치를 권장합니다.")
    print("설치 명령어: pip install selenium webdriver-manager")

class NotionCrawler:
    def __init__(self):
        """노션 크롤러 초기화"""
        self.session = requests.Session()
        # 일반적인 브라우저 헤더 설정
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
    
    def extract_detailed_content(self, soup):
        """
        노션 페이지에서 상세한 계층 구조와 콘텐츠를 추출
        
        Args:
            soup: BeautifulSoup 객체
            
        Returns:
            list: 구조화된 콘텐츠 리스트
        """
        structured_content = []
        
        # 노션의 개별 블록들을 찾기
        # 노션은 각 콘텐츠 블록을 data-block-id 속성을 가진 div로 구성
        content_blocks = soup.find_all('div', {'data-block-id': True})
        
        print(f"🔍 발견된 개별 콘텐츠 블록: {len(content_blocks)}개")
        
        # 중복 제거를 위한 집합
        seen_texts = set()
        
        for i, block in enumerate(content_blocks):
            try:
                block_info = self.analyze_notion_block_improved(block, i+1)
                if block_info and block_info['text'].strip():
                    # 중복 텍스트 제거
                    text_key = block_info['text'].strip()[:100]  # 처음 100자로 중복 체크
                    if text_key not in seen_texts:
                        seen_texts.add(text_key)
                        structured_content.append(block_info)
            except Exception as e:
                print(f"⚠️ 블록 {i+1} 처리 중 오류: {e}")
                continue
        
        # 만약 data-block-id로 찾지 못했다면 다른 방법 시도
        if not structured_content:
            print("🔄 대체 선택자로 콘텐츠 추출 시도...")
            
            # 노션의 다른 가능한 선택자들
            alternative_selectors = [
                '.notion-selectable',
                '[contenteditable]',
                '.notion-text-block',
                '.notion-header-block',
                '.notion-bulleted-list-item',
                '.notion-list-item'
            ]
            
            for selector in alternative_selectors:
                elements = soup.select(selector)
                if elements:
                    print(f"✅ {selector}로 {len(elements)}개 요소 발견")
                    for i, element in enumerate(elements):
                        try:
                            block_info = self.analyze_element_improved(element, i+1, selector)
                            if block_info and block_info['text'].strip():
                                text_key = block_info['text'].strip()[:100]
                                if text_key not in seen_texts:
                                    seen_texts.add(text_key)
                                    structured_content.append(block_info)
                        except Exception as e:
                            print(f"⚠️ 요소 {i+1} 처리 중 오류: {e}")
                            continue
                    break
        
        return structured_content
    
    def analyze_notion_block_improved(self, block, index):
        """
        개별 노션 블록을 개선된 방식으로 분석하여 타입과 콘텐츠 추출
        
        Args:
            block: BeautifulSoup 요소
            index: 블록 인덱스
            
        Returns:
            dict: 블록 정보
        """
        # 블록의 클래스 정보로 타입 판단
        class_list = block.get('class', [])
        
        # 블록 타입 결정
        block_type = 'unknown'
        if 'notion-header-block' in class_list:
            block_type = 'header'
        elif 'notion-text-block' in class_list:
            block_type = 'text'
        elif 'notion-bulleted-list-item' in class_list:
            block_type = 'bullet_list'
        elif 'notion-numbered-list-item' in class_list:
            block_type = 'numbered_list'
        elif 'notion-toggle-block' in class_list:
            block_type = 'toggle'
        elif 'notion-page-block' in class_list:
            block_type = 'page_title'
        elif 'notion-image-block' in class_list:
            block_type = 'image'
        
        # 개별 텍스트 요소들을 분리하여 추출
        text_parts = []
        
        # 헤더 블록의 경우 더 정확한 추출 방식 사용
        if block_type == 'header':
            # 헤더의 경우 contenteditable 속성을 가진 직접적인 텍스트만 추출
            header_text_elements = block.find_all(attrs={'contenteditable': True})
            
            if header_text_elements:
                # 첫 번째 contenteditable 요소가 실제 헤더 텍스트
                main_header = header_text_elements[0].get_text().strip()
                if main_header:
                    text_parts = [main_header]
            
            # contenteditable로 찾지 못한 경우 대체 방법
            if not text_parts:
                # data-content-editable-leaf 속성 확인
                leaf_elements = block.find_all(attrs={'data-content-editable-leaf': True})
                if leaf_elements:
                    for leaf in leaf_elements:
                        leaf_text = leaf.get_text().strip()
                        if leaf_text and len(leaf_text) > 3:
                            text_parts.append(leaf_text)
                            break  # 첫 번째 의미있는 텍스트만 사용
            
            # 여전히 찾지 못한 경우 직접 자식 요소 중 가장 짧은 텍스트 사용 (헤더 특성상 짧음)
            if not text_parts:
                direct_children = list(block.children)
                shortest_text = ""
                min_length = float('inf')
                
                for child in direct_children:
                    if hasattr(child, 'get_text'):
                        child_text = child.get_text().strip()
                        if child_text and 10 < len(child_text) < min_length and len(child_text) < 200:
                            shortest_text = child_text
                            min_length = len(child_text)
                
                if shortest_text:
                    text_parts = [shortest_text]
        
        else:
            # 헤더가 아닌 블록의 기존 처리 방식
            # 직접적인 텍스트 노드들 찾기
            direct_text_elements = block.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'div', 'span'], recursive=False)
            
            for element in direct_text_elements:
                # contenteditable 속성이 있는 요소들 우선적으로 처리
                if element.get('contenteditable') or element.get('data-content-editable-leaf'):
                    element_text = element.get_text().strip()
                    if element_text and len(element_text) > 3:  # 의미있는 텍스트만
                        text_parts.append(element_text)
            
            # 만약 직접적인 텍스트가 없다면 전체 텍스트 추출
            if not text_parts:
                full_text = block.get_text().strip()
                if full_text:
                    # 긴 텍스트는 문장 단위로 분리
                    if len(full_text) > 200:
                        # 문장 단위로 분리 (간단한 방식)
                        sentences = []
                        current_sentence = ""
                        for char in full_text:
                            current_sentence += char
                            if char in '.!?。' and len(current_sentence.strip()) > 10:
                                sentences.append(current_sentence.strip())
                                current_sentence = ""
                        if current_sentence.strip():
                            sentences.append(current_sentence.strip())
                        
                        # 너무 많은 문장이면 처음 3개만
                        text_parts = sentences[:3] if len(sentences) > 3 else sentences
                    else:
                        text_parts = [full_text]
        
        # 최종 텍스트 결합 (줄바꿈으로 분리)
        final_text = '\n'.join(text_parts) if text_parts else ""
        
        # 하위 요소들 분석
        sub_elements = []
        
        # 리스트 아이템들 찾기
        list_items = block.find_all(['li', 'div'], class_=re.compile(r'notion.*list.*item'))
        for item in list_items:
            item_text = item.get_text().strip()
            if item_text and item_text not in final_text:  # 중복 제거
                sub_elements.append({
                    'type': 'list_item',
                    'text': item_text
                })
        
        # 링크 찾기
        links = block.find_all('a', href=True)
        link_info = []
        for link in links:
            link_text = link.get_text().strip()
            if link_text:
                link_info.append({
                    'text': link_text,
                    'url': link.get('href')
                })
        
        return {
            'index': index,
            'type': block_type,
            'classes': class_list,
            'text': final_text,
            'text_parts': text_parts,  # 분리된 텍스트 파트들도 저장
            'sub_elements': sub_elements,
            'links': link_info,
            'html_tag': block.name
        }
    
    def analyze_element_improved(self, element, index, selector):
        """
        일반 요소를 개선된 방식으로 분석하여 콘텐츠 추출
        
        Args:
            element: BeautifulSoup 요소
            index: 요소 인덱스
            selector: 사용된 선택자
            
        Returns:
            dict: 요소 정보
        """
        class_list = element.get('class', [])
        
        # 개별 텍스트 추출
        text_parts = []
        
        # contenteditable 요소 우선 처리
        editable_elements = element.find_all(attrs={'contenteditable': True}) or element.find_all(attrs={'data-content-editable-leaf': True})
        
        if editable_elements:
            for editable in editable_elements:
                text = editable.get_text().strip()
                if text and len(text) > 3:
                    text_parts.append(text)
        
        # editable 요소가 없으면 직접 자식 요소들에서 추출
        if not text_parts:
            for child in element.children:
                if hasattr(child, 'get_text'):
                    child_text = child.get_text().strip()
                    if child_text and len(child_text) > 3:
                        text_parts.append(child_text)
        
        # 그래도 없으면 전체 텍스트
        if not text_parts:
            full_text = element.get_text().strip()
            if full_text:
                text_parts = [full_text]
        
        # 최종 텍스트 (줄바꿈으로 분리)
        final_text = '\n'.join(text_parts) if text_parts else ""
        
        # 링크 정보 추출
        links = element.find_all('a', href=True)
        link_info = []
        for link in links:
            link_text = link.get_text().strip()
            if link_text:
                link_info.append({
                    'text': link_text,
                    'url': link.get('href')
                })
        
        return {
            'index': index,
            'selector': selector,
            'classes': class_list,
            'text': final_text,
            'text_parts': text_parts,
            'links': link_info,
            'html_tag': element.name
        }
    
    def crawl_with_selenium(self, url):
        """
        Selenium을 사용하여 동적 콘텐츠가 포함된 노션 페이지 크롤링
        
        Args:
            url (str): 크롤링할 노션 페이지 URL
            
        Returns:
            dict: 추출된 콘텐츠 정보
        """
        if not SELENIUM_AVAILABLE:
            print("❌ Selenium이 설치되지 않았습니다. requests 방식으로 폴백합니다.")
            return self.crawl_notion_page(url)
        
        driver = None
        try:
            print(f"🔍 Selenium을 사용한 노션 페이지 크롤링 시작: {url}")
            
            # Chrome 옵션 설정
            chrome_options = Options()
            chrome_options.add_argument('--headless')  # 브라우저 창 숨기기
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
            
            # 드라이버 초기화 (자동으로 Chrome 드라이버 다운로드)
            driver = webdriver.Chrome(service=webdriver.chrome.service.Service(ChromeDriverManager().install()), options=chrome_options)
            driver.set_page_load_timeout(30)
            
            # 페이지 로드
            driver.get(url)
            
            print("⏳ 페이지 로딩 대기 중...")
            time.sleep(8)  # 더 긴 로딩 시간
            
            # 스크롤을 통해 모든 콘텐츠 로드
            print("📜 페이지 스크롤하여 모든 콘텐츠 로드...")
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(3)
            driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(2)
            
            # 노션 콘텐츠가 로드될 때까지 대기
            try:
                wait = WebDriverWait(driver, 20)
                # 다양한 선택자로 콘텐츠 로딩 확인
                selectors_to_try = [
                    "div[data-block-id]",
                    ".notion-page-content",
                    ".notion-selectable",
                    ".notion-header-block"
                ]
                
                content_found = False
                for selector in selectors_to_try:
                    try:
                        elements = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, selector)))
                        if elements:
                            print(f"✅ 콘텐츠 요소 발견: {selector} ({len(elements)}개)")
                            content_found = True
                            break
                    except TimeoutException:
                        continue
                
                if not content_found:
                    print("⚠️ 특정 콘텐츠 요소를 찾지 못했지만 페이지 파싱을 계속합니다.")
                
            except TimeoutException:
                print("⚠️ 페이지 로딩 타임아웃, 현재 상태로 파싱을 시도합니다.")
            
            # 토글 버튼들을 찾아서 클릭하여 모든 콘텐츠 펼치기
            print("🔓 토글 섹션들을 펼치는 중...")
            try:
                # 토글 버튼 선택자들
                toggle_selectors = [
                    'div[aria-expanded="false"]',
                    'div[aria-label="열기"]',
                    '.notion-list-item-box-left div[role="button"]'
                ]
                
                expanded_toggles = 0
                for selector in toggle_selectors:
                    try:
                        toggle_buttons = driver.find_elements(By.CSS_SELECTOR, selector)
                        print(f"🎯 발견된 토글 버튼 ({selector}): {len(toggle_buttons)}개")
                        
                        for i, button in enumerate(toggle_buttons):
                            try:
                                # 버튼이 화면에 보이는지 확인
                                if button.is_displayed() and button.is_enabled():
                                    # 스크롤하여 버튼을 화면에 표시
                                    driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", button)
                                    time.sleep(0.5)
                                    
                                    # 클릭 시도
                                    try:
                                        button.click()
                                        expanded_toggles += 1
                                        print(f"✅ 토글 {i+1} 펼침 완료")
                                        time.sleep(1)  # 콘텐츠 로딩 대기
                                    except Exception as click_error:
                                        # JavaScript로 클릭 재시도
                                        try:
                                            driver.execute_script("arguments[0].click();", button)
                                            expanded_toggles += 1
                                            print(f"✅ 토글 {i+1} 펼침 완료 (JS)")
                                            time.sleep(1)
                                        except Exception as js_error:
                                            print(f"⚠️ 토글 {i+1} 클릭 실패: {js_error}")
                            except Exception as e:
                                print(f"⚠️ 토글 버튼 {i+1} 처리 중 오류: {e}")
                                continue
                        
                        if expanded_toggles > 0:
                            break  # 토글을 찾았으면 다른 선택자는 시도하지 않음
                            
                    except Exception as e:
                        print(f"⚠️ 토글 선택자 {selector} 처리 중 오류: {e}")
                        continue
                
                print(f"📊 총 {expanded_toggles}개의 토글 섹션을 펼쳤습니다.")
                
                if expanded_toggles > 0:
                    # 토글을 펼친 후 추가 로딩 시간
                    print("⏳ 펼쳐진 콘텐츠 로딩 대기...")
                    time.sleep(5)
                    
                    # 다시 스크롤하여 모든 콘텐츠 확인
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(2)
                    driver.execute_script("window.scrollTo(0, 0);")
                    time.sleep(2)
                
            except Exception as e:
                print(f"⚠️ 토글 처리 중 오류 발생: {e}")
            
            # 추가 로딩 시간
            time.sleep(3)
            
            # 페이지 소스 가져오기
            page_source = driver.page_source
            print(f"📄 페이지 소스 크기: {len(page_source)} 문자")
            
            # BeautifulSoup으로 파싱
            soup = BeautifulSoup(page_source, 'html.parser')
            
            # 크롤링 결과 저장용 딕셔너리
            crawl_result = {
                'url': url,
                'title': '',
                'structured_content': [],
                'images': [],
                'metadata': {},
                'method': 'selenium_detailed',
                'expanded_toggles': expanded_toggles
            }
            
            # 페이지 제목 추출
            title_element = soup.find('title')
            if title_element:
                crawl_result['title'] = title_element.get_text().strip()
                print(f"📌 페이지 제목: {crawl_result['title']}")
            
            # 상세한 콘텐츠 구조 추출
            crawl_result['structured_content'] = self.extract_detailed_content(soup)
            
            # 이미지 추출
            images = soup.find_all('img', src=True)
            for img in images[:15]:  # 상위 15개 이미지만 처리
                src = img['src']
                alt = img.get('alt', '')
                full_url = urljoin(url, src)
                crawl_result['images'].append({
                    'src': full_url,
                    'alt': alt
                })
            
            # 메타데이터 추출
            meta_tags = soup.find_all('meta')
            for meta in meta_tags:
                name = meta.get('name') or meta.get('property')
                content = meta.get('content')
                if name and content:
                    crawl_result['metadata'][name] = content
            
            print(f"📊 상세 Selenium 크롤링 완료:")
            print(f"   - 구조화된 콘텐츠 블록: {len(crawl_result['structured_content'])}개")
            print(f"   - 이미지: {len(crawl_result['images'])}개")
            print(f"   - 메타데이터: {len(crawl_result['metadata'])}개")
            print(f"   - 펼쳐진 토글: {expanded_toggles}개")
            
            return crawl_result
            
        except WebDriverException as e:
            print(f"❌ Selenium 드라이버 오류: {e}")
            print("🔄 requests 방식으로 폴백합니다.")
            return self.crawl_notion_page(url)
        except Exception as e:
            print(f"❌ Selenium 크롤링 오류: {e}")
            print("🔄 requests 방식으로 폴백합니다.")
            return self.crawl_notion_page(url)
        finally:
            if driver:
                driver.quit()
    
    def crawl_notion_page(self, url):
        """
        노션 페이지를 크롤링하여 콘텐츠 추출 (requests 방식)
        
        Args:
            url (str): 크롤링할 노션 페이지 URL
            
        Returns:
            dict: 추출된 콘텐츠 정보
        """
        try:
            print(f"🔍 노션 페이지 크롤링 시작 (requests): {url}")
            
            # 페이지 요청
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            print(f"✅ HTTP 응답 코드: {response.status_code}")
            print(f"📄 콘텐츠 타입: {response.headers.get('content-type', 'Unknown')}")
            
            # HTML 파싱
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # 크롤링 결과 저장용 딕셔너리
            crawl_result = {
                'url': url,
                'title': '',
                'content': '',
                'text_blocks': [],
                'links': [],
                'images': [],
                'metadata': {},
                'method': 'requests'
            }
            
            # 페이지 제목 추출
            title_element = soup.find('title')
            if title_element:
                crawl_result['title'] = title_element.get_text().strip()
                print(f"📌 페이지 제목: {crawl_result['title']}")
            
            # 노션 특정 콘텐츠 영역 찾기
            # 노션은 주로 특정 클래스나 ID를 가진 div에 콘텐츠를 담음
            content_selectors = [
                'div[data-block-id]',  # 노션 블록
                '.notion-page-content',
                '.notion-page-block',
                '[role="main"]',
                'main',
                'article'
            ]
            
            content_elements = []
            for selector in content_selectors:
                elements = soup.select(selector)
                if elements:
                    content_elements.extend(elements)
                    print(f"🎯 발견된 콘텐츠 블록 ({selector}): {len(elements)}개")
            
            # 텍스트 콘텐츠 추출
            if content_elements:
                for element in content_elements[:10]:  # 상위 10개 요소만 처리
                    text = element.get_text().strip()
                    if text and len(text) > 10:  # 의미있는 텍스트만 저장
                        crawl_result['text_blocks'].append({
                            'tag': element.name,
                            'class': element.get('class', []),
                            'text': text[:500] + '...' if len(text) > 500 else text  # 긴 텍스트는 축약
                        })
            else:
                # 일반적인 텍스트 추출
                body = soup.find('body')
                if body:
                    all_text = body.get_text()
                    # 공백 정리
                    clean_text = re.sub(r'\s+', ' ', all_text).strip()
                    crawl_result['content'] = clean_text[:1000] + '...' if len(clean_text) > 1000 else clean_text
                    print(f"📝 전체 텍스트 길이: {len(clean_text)} 문자")
            
            # 링크 추출
            links = soup.find_all('a', href=True)
            for link in links[:20]:  # 상위 20개 링크만 처리
                href = link['href']
                text = link.get_text().strip()
                if text:
                    full_url = urljoin(url, href)
                    crawl_result['links'].append({
                        'text': text,
                        'url': full_url
                    })
            
            # 이미지 추출
            images = soup.find_all('img', src=True)
            for img in images[:10]:  # 상위 10개 이미지만 처리
                src = img['src']
                alt = img.get('alt', '')
                full_url = urljoin(url, src)
                crawl_result['images'].append({
                    'src': full_url,
                    'alt': alt
                })
            
            # 메타데이터 추출
            meta_tags = soup.find_all('meta')
            for meta in meta_tags:
                name = meta.get('name') or meta.get('property')
                content = meta.get('content')
                if name and content:
                    crawl_result['metadata'][name] = content
            
            print(f"📊 requests 크롤링 완료:")
            print(f"   - 텍스트 블록: {len(crawl_result['text_blocks'])}개")
            print(f"   - 링크: {len(crawl_result['links'])}개")
            print(f"   - 이미지: {len(crawl_result['images'])}개")
            print(f"   - 메타데이터: {len(crawl_result['metadata'])}개")
            
            return crawl_result
            
        except requests.exceptions.RequestException as e:
            print(f"❌ 네트워크 오류: {e}")
            return None
        except Exception as e:
            print(f"❌ 크롤링 오류: {e}")
            return None
    
    def save_text_only(self, result, filename="notion_content_text_only.txt"):
        """
        크롤링 결과에서 텍스트만 추출하여 별도 파일로 저장
        
        Args:
            result: 크롤링 결과 딕셔너리
            filename: 저장할 파일명
        """
        if not result or 'structured_content' not in result:
            print("❌ 텍스트 추출할 결과가 없습니다.")
            return
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                # 헤더 정보 작성
                f.write("="*80 + "\n")
                f.write(f"노션 페이지 텍스트 추출 결과\n")
                f.write("="*80 + "\n\n")
                
                if result.get('title'):
                    f.write(f"📌 제목: {result['title']}\n")
                
                f.write(f"🔗 URL: {result['url']}\n")
                f.write(f"🛠️ 크롤링 방식: {result.get('method', 'unknown')}\n")
                
                if result.get('expanded_toggles'):
                    f.write(f"🔓 펼쳐진 토글: {result['expanded_toggles']}개\n")
                
                f.write(f"📄 총 블록 수: {len(result['structured_content'])}개\n")
                f.write("\n" + "="*80 + "\n\n")
                
                # 구조화된 콘텐츠에서 텍스트 추출
                current_header_level = 0
                
                for i, content in enumerate(result['structured_content'], 1):
                    block_type = content.get('type', 'unknown')
                    text = content.get('text', '').strip()
                    
                    if not text:
                        continue
                    
                    # 블록 타입에 따른 포맷팅
                    if block_type == 'page_title':
                        f.write(f"🏷️ {text}\n")
                        f.write("-" * len(text) + "\n\n")
                        
                    elif block_type == 'header':
                        f.write(f"\n📋 {text}\n")
                        f.write("=" * min(len(text), 50) + "\n\n")
                        current_header_level = 1
                        
                    elif 'sub_header' in content.get('classes', []) or block_type == 'sub_header':
                        f.write(f"\n🔸 {text}\n")
                        f.write("-" * min(len(text), 30) + "\n\n")
                        current_header_level = 2
                        
                    elif 'bulleted_list' in content.get('classes', []) or block_type == 'bullet_list':
                        f.write(f"  • {text}\n")
                        
                    elif 'numbered_list' in content.get('classes', []) or block_type == 'numbered_list':
                        f.write(f"  {i}. {text}\n")
                        
                    elif 'quote' in content.get('classes', []) or block_type == 'quote':
                        f.write(f"\n💬 \"{text}\"\n\n")
                        
                    elif 'table' in content.get('classes', []) or block_type == 'table':
                        f.write(f"\n📊 표 데이터:\n{text}\n\n")
                        
                    elif block_type == 'text':
                        # 일반 텍스트는 문단으로 처리
                        if len(text) > 20:  # 의미있는 텍스트만
                            f.write(f"{text}\n\n")
                        
                    else:
                        # 기타 블록들
                        if len(text) > 10:  # 의미있는 텍스트만
                            f.write(f"{text}\n")
                    
                    # 링크 정보가 있으면 추가
                    if content.get('links'):
                        f.write("\n🔗 관련 링크:\n")
                        for link in content['links'][:3]:  # 상위 3개만
                            f.write(f"   - {link['text']}: {link['url']}\n")
                        f.write("\n")
                
                # 이미지 정보 추가
                if result.get('images'):
                    f.write("\n" + "="*50 + "\n")
                    f.write("🖼️ 포함된 이미지들\n")
                    f.write("="*50 + "\n\n")
                    for i, img in enumerate(result['images'][:10], 1):
                        alt_text = img.get('alt', '이미지')
                        f.write(f"{i}. {alt_text}\n")
                        f.write(f"   URL: {img['src']}\n\n")
                
                f.write("\n" + "="*80 + "\n")
                f.write("텍스트 추출 완료\n")
                f.write("="*80 + "\n")
            
            print(f"📝 텍스트만 추출하여 {filename} 파일로 저장완료!")
            
        except Exception as e:
            print(f"❌ 텍스트 저장 중 오류 발생: {e}")
    
    def extract_clean_text(self, result):
        """
        크롤링 결과에서 순수한 텍스트만 추출하여 문자열로 리턴 (임베딩용)
        
        Args:
            result: 크롤링 결과 딕셔너리
            
        Returns:
            str: 깔끔하게 정리된 텍스트 문자열
        """
        if not result or 'structured_content' not in result:
            return ""
        
        text_parts = []
        
        # 제목 추가
        if result.get('title'):
            text_parts.append(f"{result['title']}\n")
        
        # 구조화된 콘텐츠에서 텍스트 추출
        for content in result['structured_content']:
            block_type = content.get('type', 'unknown')
            text = content.get('text', '').strip()
            
            if not text or len(text) < 5:  # 너무 짧은 텍스트 제외
                continue
            
            # 블록 타입에 따른 간단한 포맷팅
            if block_type == 'page_title':
                text_parts.append(f"{text}\n")
                
            elif block_type == 'header':
                text_parts.append(f"\n{text}\n")
                
            elif 'sub_header' in content.get('classes', []) or block_type == 'sub_header':
                text_parts.append(f"\n{text}\n")
                
            elif 'bulleted_list' in content.get('classes', []) or block_type == 'bullet_list':
                text_parts.append(f"• {text}")
                
            elif 'numbered_list' in content.get('classes', []) or block_type == 'numbered_list':
                text_parts.append(f"{text}")
                
            elif 'quote' in content.get('classes', []) or block_type == 'quote':
                text_parts.append(f'"{text}"')
                
            elif 'table' in content.get('classes', []) or block_type == 'table':
                # 표 데이터는 포함하되 포맷팅 간소화
                text_parts.append(f"{text}")
                
            elif block_type == 'text':
                # 일반 텍스트는 문단으로 처리
                if len(text) > 15:  # 의미있는 텍스트만
                    text_parts.append(f"{text}")
                    
            else:
                # 기타 블록들
                if len(text) > 10:  # 의미있는 텍스트만
                    text_parts.append(f"{text}")
        
        # 최종 텍스트 결합
        final_text = '\n'.join(text_parts)
        
        # 불필요한 공백과 줄바꿈 정리
        final_text = '\n'.join(line.strip() for line in final_text.split('\n') if line.strip())
        
        # 연속된 줄바꿈 정리 (최대 2개까지만)
        import re
        final_text = re.sub(r'\n{3,}', '\n\n', final_text)
        
        return final_text
    
    def print_crawl_result(self, result):
        """크롤링 결과를 보기 좋게 출력"""
        if not result:
            print("❌ 크롤링 결과가 없습니다.")
            return
        
        print("\n" + "="*80)
        print("📋 노션 페이지 크롤링 결과")
        print("="*80)
        
        print(f"\n🔗 URL: {result['url']}")
        print(f"🛠️ 크롤링 방식: {result.get('method', 'unknown')}")
        
        if result.get('expanded_toggles'):
            print(f"🔓 펼쳐진 토글: {result['expanded_toggles']}개")
        
        if result['title']:
            print(f"\n📌 제목: {result['title']}")
        
        # 구조화된 콘텐츠가 있는 경우
        if 'structured_content' in result and result['structured_content']:
            print(f"\n📄 구조화된 콘텐츠 ({len(result['structured_content'])}개 블록):")
            for i, content in enumerate(result['structured_content'][:30], 1):  # 상위 30개만 출력
                print(f"\n   📍 블록 {i} [{content.get('type', 'unknown')}]:")
                
                # text_parts가 있으면 그것을 우선 사용
                if content.get('text_parts') and len(content['text_parts']) > 1:
                    print(f"      📝 텍스트 파트들 ({len(content['text_parts'])}개):")
                    for j, part in enumerate(content['text_parts'][:5], 1):  # 상위 5개 파트만
                        preview = part[:100] + '...' if len(part) > 100 else part
                        print(f"        {j}. {preview}")
                else:
                    # 일반 텍스트 출력
                    text_preview = content['text'][:200] + '...' if len(content['text']) > 200 else content['text']
                    # 줄바꿈을 실제로 표시
                    formatted_text = text_preview.replace('\n', '\n           ')
                    print(f"      텍스트: {formatted_text}")
                
                if content.get('sub_elements'):
                    print(f"      📋 하위 요소들:")
                    for j, sub in enumerate(content['sub_elements'][:3], 1):
                        sub_preview = sub.get('text', '')[:80] + '...' if len(sub.get('text', '')) > 80 else sub.get('text', '')
                        print(f"        {j}. {sub_preview}")
                
                if content.get('links'):
                    print(f"      🔗 링크들:")
                    for link in content['links'][:3]:
                        print(f"        🔗 {link['text']} -> {link['url']}")
        
        # 기존 text_blocks가 있는 경우
        elif 'text_blocks' in result and result['text_blocks']:
            print(f"\n📄 텍스트 블록들 ({len(result['text_blocks'])}개):")
            for i, block in enumerate(result['text_blocks'][:5], 1):  # 상위 5개만 출력
                print(f"\n   {i}. [{block['tag']}] {block['text']}")
        
        if result.get('content'):
            print(f"\n📝 전체 콘텐츠 (요약):\n{result['content']}")
        
        if result.get('images'):
            print(f"\n🖼️ 발견된 이미지들 ({len(result['images'])}개):")
            for i, img in enumerate(result['images'][:5], 1):  # 상위 5개만 출력
                print(f"   {i}. {img['alt']} -> {img['src']}")
        
        if result.get('metadata'):
            print(f"\n📊 메타데이터 ({len(result['metadata'])}개):")
            for key, value in list(result['metadata'].items())[:10]:  # 상위 10개만 출력
                print(f"   {key}: {value}")
        
        print("\n" + "="*80)
