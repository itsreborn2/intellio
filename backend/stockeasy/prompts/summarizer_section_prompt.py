from datetime import datetime
from langchain_core.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from typing import Any, Dict, List, Optional
from stockeasy.models.agent_io import RetrievedTelegramMessage
from stockeasy.prompts.telegram_prompts import format_telegram_messages

# --- START: 섹션별 종합 분석 프롬프트 정의 ---

PROMPT_GENERATE_SECTION_CONTENT = """
당신은 투자 리서치 보고서 전문 작성가입니다. 주어진 섹션 정보와 분석 데이터를 바탕으로 해당 섹션의 내용을 작성해야 합니다.

# 작업 목표
아래 제공된 섹션 정보와 분석 데이터를 바탕으로 투자 리서치 보고서의 해당 섹션 내용을 전문적으로 작성하세요.

# 입력 정보
원래 질문: {query}

섹션 제목: {section_title}
섹션 설명: {section_description}
하위섹션 목록: {subsections_info}

<수행한 검색 및 분석 결과 요약>
{all_analyses}
</수행한 검색 및 분석 결과 요약>

# 섹션 작성 지침
1. **섹션 목적 집중**: 해당 섹션의 목적과 범위에 맞게 내용을 집중적으로 작성하세요.
2. **데이터 기반 분석**: 제공된 분석 데이터에서 해당 섹션과 관련된 정보를 선별하여 활용하세요.
3. **논리적 구성**: 섹션 내용을 논리적으로 구성하고, 필요한 경우 소제목을 활용하여 구조화하세요.
4. **전문성 표현**: 금융 및 투자 분야의 전문 용어를 적절히 활용하여 내용의 전문성을 높이세요.
5. **시각적 구조화**: 글머리 기호, 표, 중요 정보 강조 등을 활용하여 내용을 시각적으로 구조화하세요.
6. **말투** : 항상 존대말투를 사용하세요.

## 내부DB 데이터 처리 지침
1. **채팅 내용 직접 인용 금지**: 내부DB 데이터의 채팅 내용을 원문 그대로 직접 인용하지 마세요.
2. **전문적 언어로 재구성**: 채팅 형식의 정보는 반드시 전문적인 금융 리서치 보고서 언어로 재구성하세요.
3. **정보 추출 및 변환**: 
   - "~라는 내부 언급처럼" 같은 인용 형식을 피하고, 사실을 객관적으로 서술하세요.
   - 예시: "천궁-II 해외 계약이 1분기부터 매출로 인식되어 실적에 긍정적인 영향을 미치고 있습니다."
4. **출처 표기 방식**: 
   - 내부DB 정보를 활용할 때는 "내부 분석에 따르면", "내부 데이터 기반 분석 결과" 등으로 출처만 간략히 언급하세요.
   - 개별 채팅 메시지의 시간이나 작성자 정보를 포함하지 마세요.
   - **핵심 내용에만 인용 표시**: 
     * 문단의 핵심 주장이나 중요한 사실에만 인용을 표시하세요.
     * 연속된 문장에서 같은 출처를 반복해서 인용하지 마세요.
     * 문단 시작에 출처를 한 번만 표시하고, 이후 내용은 출처 없이 서술하세요.
     * 예시:
       ```
       [잘못된 예]
       노머스는 아티스트 IP를 활용한 엔터테크 기업입니다 (유진투자증권, 2024-10-23). 
       주요 사업은 콘서트 진행, MD 상품 판매, 팬덤 플랫폼 운영입니다 (내부DB, 2025-03-27).
       다양한 기획사 소속 아티스트와 협력하는 전략을 취하고 있습니다 (SK, 2025-03-06).

       [올바른 예]
       노머스는 아티스트 IP를 활용한 엔터테크 기업으로, 앨범 판매, 공연 주최 등 아티스트의 직접 활동뿐만 아니라 
       콘텐츠 제작, MD 상품 제작 및 판매, 유료 메시지 서비스 및 팬클럽과 같은 팬덤 플랫폼을 통한 IP 사용 권리 등을 
       계약 형태로 취득하여 간접 활동을 지원합니다 (유진투자증권, 2024-10-23).
       ```
5. **비전문적 표현 제거**: 
   - "~네요", "~인듯", "~같아요" 등 대화체 표현을 제거하고 "~입니다", "~확인됩니다" 등 공식적인 표현으로 대체하세요.
   - 이모티콘, 속어, 줄임말 등을 모두 제거하고 공식적인 용어로 대체하세요.

## 재무 및 실적 데이터 시각화 지침
1. **반드시 테이블 형식 사용**:
   - 모든 재무 지표, 매출, 실적 데이터는 반드시 마크다운 테이블로 구조화하세요.
   - 예시:
     ```
     | 구분 | 2023년 | 2024년 | 증감률(%) |
     |-----|-------|-------|----------|
     | 매출액 | 1,200억 | 1,500억 | +25.0 |
     | 영업이익 | 150억 | 180억 | +20.0 |
     | 순이익 | 100억 | 120억 | +20.0 |
     ```

2. **시계열 데이터 표현**:
   - 분기별/연도별 추이는 다음과 같이 명확한 테이블로 제시하세요:
     ```
     | 지표 | 1Q23 | 2Q23 | 3Q23 | 4Q23 | 1Q24 | 증감률(QoQ) | 증감률(YoY) |
     |-----|------|------|------|------|------|------------|------------|
     | 매출액 | 300억 | 320억 | 290억 | 310억 | 350억 | +12.9% | +16.7% |
     ```

3. **비율 및 증감률 강조**:
   - 전년 대비(YoY), 전기 대비(QoQ) 변화율은 항상 별도 열로 포함하고 증감 방향에 따라 +/- 기호를 사용하세요.
   - 주요 증감은 굵은 글씨로 강조하세요.

4. **텍스트 형태의 차트 표현**:
   - 텍스트로 간단한 차트를 표현할 때는 다음과 같은 형식을 사용하세요:
     ```
     매출 추이 (단위: 억원)
     2021: ■■■■■■■■ (800)
     2022: ■■■■■■■■■■ (1,000)
     2023: ■■■■■■■■■■■■ (1,200)
     2024E: ■■■■■■■■■■■■■■■ (1,500)
     ```

5. **섹터 및 경쟁사 비교**:
   - 경쟁사와의 비교는 항상 표 형식으로 제시하고, 비교 우위점을 강조하세요.
     ```
     | 기업 | 매출액(억원) | 영업이익률(%) | 시장점유율(%) |
     |-----|------------|-------------|------------|
     | 당사 | 1,500 | 12.0 | 25.0 |
     | A사 | 1,300 | 10.5 | 22.0 |
     | B사 | 1,800 | 9.0 | 30.0 |
     ```
## **재무데이터 사용 소스 지침**
1. 매출액, 영업이익, 당기순이익 데이터는 **반드시 <사업보고서, 재무 분석 정보> 소스의 '최근 분기 실적' 테이블 데이터 사용**

## 심층 분석 접근 방법
1. **다층적 정보 통합 및 교차 검증**
   - 각 출처의 정보를 단순히 나열하지 말고, 서로 다른 출처의 정보를 교차 검증하세요
   - 각 정보 출처와 발행 시점을 명확히 표기하세요 (예: "프로스트 앤 설리번의 2023년 9월 보고서")
   - 상충되는 정보가 있다면 이를 명시하고, 가능한 원인과 함께 어떤 관점이 더 신뢰할 수 있는지 분석하세요
   - 시간적 흐름에 따라 정보를 정렬하여 변화하는 추세와 패턴을 파악하세요
   - 정보 출처의 우선순위는 사업보고서 > 기업리포트 > 내부DB > 비공개자료 순으로 고려하세요
   - 섹션별 데이터 소스 참고 우선순위:
     * 지난 실적/재무 성과 분석: <사업보고서, 재무 분석 정보> 우선 참조
     * 예상 실적/미래 전망: <기업리포트> 우선 참조
     * 산업동향/시장전망: <산업,섹터 분석> 우선 참조

2. **체계적인 문단 구성**
   - 각 문단은 하나의 핵심 주제를 중심으로 명확하고 간결하게 작성하세요. 필요에 따라 짧은 문장이나 목록을 활용하여 가독성을 높이세요.
   - 문단 시작에는 핵심 주장이나 요약을 먼저 제시하고, 이후 상세 설명과 근거를 제공하세요
   - 대제목-중제목-소제목의 3단계 계층적 구조를 활용하여 정보를 체계화하세요
   - 각 섹션 말미에는 정리 박스를 추가하여 중요 포인트를 강조하세요

3. **인과관계 및 연관성 분석**
   - 단순한 현상 설명을 넘어 '왜' 그런 현상이 발생했는지 분석하세요
   - 각 문단 내에서 원인 → 현상 → 결과 → 시사점의 논리적 흐름을 구축하세요
   - "이로 인해", "그 결과", "따라서" 등의 연결어를 활용하여 논리적 흐름을 명확히 하세요
   - 복잡한 인과관계는 화살표 다이어그램이나 흐름도를 통해 시각화하세요
   - 내부DB 정보와 공식 보고서의 관계성, 업계 동향과 개별 기업 성과의 관계성 등을 명확히 드러내세요

4. **정보의 신뢰도 표시 및 불확실성 인식**
   - 확실성 정도에 따른 표현을 차별화하세요:
     - 확실한 정보: "~임을 확인함", "~로 입증됨"
     - 불확실한 정보: "~로 추정됨", "~일 가능성이 있음", "~로 예상됨"
   - 정보의 신뢰도를 명시적으로 표시하세요:
   - 결론을 내리기에 불충분한 정보가 있다면 이를 명확히 밝히세요
   - 향후 모니터링이 필요한 핵심 지표나 이벤트를 제안하세요

5. **시각적 구조화 및 정보 강조**
   - 굵은 글씨(Bold)를 활용하여 핵심 문구와 중요 수치를 강조하세요
   - 글머리 기호(•)와 부기호(-)를 활용하여 계층적 정보를 구조화하세요
   - 표 형식을 활용하여 경쟁기업 비교, 기술별 장단점, 시장별 성장률 등을 명확히 제시하세요
   - 시간순 정보는 타임라인 형식으로 제시하여 변화와 발전 과정을 시각화하세요
   - SWOT 분석이나 레이더 차트 등을 활용하여 종합적 경쟁력을 평가하세요

## 추가 지침
- 분석의 근거가 되는 데이터(수치, 시장 자료, 보고서 인용 등)를 명확히 제시하고, 반드시 출처와 시점을 함께 명시하세요.
- 각 섹션의 시작 부분에는 해당 섹션의 목적과 범위를 명시하여 독자의 이해를 돕고, 끝 부분에는 정리를 제공하세요.
- 제목에 일관된 번호 체계를 적용하고(1., 1.1, 1.1.1 등), 제목 중복을 피하세요.
- 각 섹션은 '현황 → 분석 → 시사점 → 전망'의 일관된 구조를 따르도록 구성하세요.
- 정량적 데이터와 정성적 분석을 균형 있게 통합하여 설득력을 높이세요.
- 단순한 정보 나열을 넘어, 각 분석 항목 간의 연관성을 파악하고 종합적인 시각에서 기업의 경쟁력을 평가하는 데 집중하세요.
- 정보의 한계나 불확실성이 있다면 명시하고, 이에 대한 합리적인 추론이나 가정을 제시하세요.
- 재무 성과 분석은 제외하고 기업의 기본체력과 경쟁력에 집중하세요.
- **각 섹션 끝에는 반드시 "정리" 박스를 추가하여 주요 포인트를 3-5개 항목으로 정리하세요.**
- **분석된 내용을 바탕으로 풍부하고 상세하게 서술하되, 핵심 아이디어를 중심으로 명료하게 전달하세요. 단순한 문장 나열보다는 논리적인 흐름과 구조를 갖추어 가독성을 높이세요. 필요한 경우 요점이나 목록을 활용하여 정보를 효과적으로 전달하세요.**
- **요청된 섹션의 내용만 작성하고, 다른 섹션 제목이나 내용은 포함하지 마세요.**


이제 "{section_title}" 섹션의 내용을 작성해주세요.
"""

DEEP_RESEARCH_USER_PROMPT = """
사용자 질문: {query}
오늘일자: {query_date}
종목코드: {stock_code}
종목명: {stock_name}
질문 의도: {primary_intent}
질문 복잡도: {complexity}
기대 답변 유형: {expected_answer_type}

{sources_info}
"""

def create_all_section_content(stock_code: Optional[str], stock_name: Optional[str],
                telegram_data: Dict[str, Any],
                report_data: List[Dict[str, Any]], confidential_data: List[Dict[str, Any]],
                financial_data: Dict[str, Any],
                revenue_breakdown_data: str,
                industry_data: List[Dict[str, Any]], integrated_knowledge: Optional[Any],
                web_search_data: List[Dict[str, Any]],
                ) -> ChatPromptTemplate:
        """요약을 위한 프롬프트 생성"""
        
        # 소스 정보 형식화
        sources_info = ""
        
        # 재무 정보
 
        if financial_data:
            sources_info += "------\n<사업보고서, 재무 분석 정보>\n"
            llm_response = financial_data.get("llm_response", "")
            if llm_response:
                sources_info += f"{llm_response}\n\n"
            else:
                sources_info += "재무 분석 결과가 없습니다.\n\n"
            
            sources_info += "</사업보고서, 재무 분석 정보>\n"


        if revenue_breakdown_data and len(revenue_breakdown_data) > 0:
            sources_info += "------\n<매출 및 수주 현황>\n"
            sources_info += f"{revenue_breakdown_data}\n\n"
            sources_info += "</매출 및 수주 현황>\n"
        
        
        # 기업 리포트
        if report_data:
            analysis = report_data.get("analysis", {})
            sources_info += "------\n<기업리포트>\n"
            if analysis:
                # 전체 소스를 다 줄게 아니라, 기업리포트 에이전트가 출력한 결과만 전달.
                # 아.. 인용처리가 애매해지네.
                # 일단은 기업리포트 결과만 남겨보자.
                sources_info += f" - 투자의견:\n{analysis.get('investment_opinions', '')}\n\n"
                sources_info += f" - 종합의견:\n{analysis.get('opinion_summary', '')}\n\n"
                sources_info += f" - 최종결과:\n{analysis.get('llm_response', '')}\n\n"
            else:
                searched_reports = report_data.get("searched_reports", [])
                for report in searched_reports[:5]:
                    report_info = report.get("content", "")
                    report_source = report.get("source", "미상")
                    report_date = report.get("publish_date", "날짜 미상")
                    report_page = f"{report.get('page', '페이지 미상')} p"
                    sources_info += f"[출처: {report_source}, {report_date}, {report_page}]\n{report_info}\n\n"
            sources_info += "</기업리포트>\n"                    

        # 산업 동향(일단 미구현. 산업리포트 에이전트 추가 후에 풀것)
        if industry_data:
            analysis = industry_data.get("analysis", {})
            sources_info += "------\n<산업,섹터 분석>\n"
            if analysis:
                sources_info += f" - 최종결과:\n{analysis.get('llm_response', '')}\n\n"
            else:
                searched_reports = industry_data.get("searched_reports", [])
                for report in searched_reports[:5]:
                    report_info = report.get("content", "")
                    report_source = report.get("source", "미상")
                    report_date = report.get("publish_date", "날짜 미상")
                    report_page = f"{report.get('page', '페이지 미상')} p"
                    sources_info += f"[출처: {report_source}, {report_date}, {report_page}]\n{report_info}\n\n"
            sources_info += "</산업,섹터 분석>\n"

         # 비공개 리포트
        if confidential_data:
            analysis = confidential_data.get("analysis", {})
            sources_info += "------\n<비공개자료>\n"
            if analysis:
                # 전체 소스를 다 줄게 아니라, 기업리포트 에이전트가 출력한 결과만 전달.
                # 아.. 인용처리가 애매해지네.
                # 일단은 기업리포트 결과만 남겨보자.
                sources_info += f" - 최종결과:\n{analysis.get('llm_response', '')}\n\n"
            else:
                searched_reports = confidential_data.get("searched_reports", [])
                for report in searched_reports[:5]:
                    report_info = report.get("content", "")
                    report_source = report.get("source", "미상")
                    report_page = f"{report.get('page', '페이지 미상')} p"
                    #sources_info += f"[출처: {report_source}, {report_date}, {report_page}]\n{report_info}\n\n"         
                    sources_info += f"[출처: {report_source}, {report_page}]\n{report_info}\n\n"         
            sources_info += "</비공개자료>\n"

        # 텔레그램 메시지
        if telegram_data:
            formatted_msgs = format_telegram_messages(telegram_data, stock_code, stock_name)
            sources_info += f"------\n<내부DB>\n"
            sources_info += f"{formatted_msgs}\n\n"
            sources_info += "</내부DB>\n"

        if web_search_data:
            web_search_summary = web_search_data.get("summary", "")
            sources_info += "------\n<웹 검색 결과>\n"
            sources_info += f"{web_search_summary}\n\n"
            sources_info += "</웹 검색 결과>\n"
        
        # 통합된 지식
        if integrated_knowledge:
            sources_info += "------\n<통합된 지식>\n"
            sources_info += f"{integrated_knowledge}\n\n"
            sources_info += "</통합된 지식>\n"

        
        # 정보가 없는 경우
        if not sources_info:
            sources_info = "검색된 정보가 없습니다. 질문에 관련된 정보를 찾을 수 없습니다."
        
        
        return sources_info

def format_other_agent_data(agent_results: Dict[str, Any], 
                            stock_code: Optional[str] = None, 
                            stock_name: Optional[str] = None) -> str:
      """
      다른 에이전트들의 결과 데이터를 create_all_section_content 함수와 유사한 형태로 포맷합니다.
      report_analyzer 데이터는 제외합니다.
      """
      sources_info_parts = []

      # Financial Analyzer 데이터
      financial_data = agent_results.get("financial_analyzer", {}).get("data", {})
      if financial_data:
          part = "------\n<사업보고서, 재무 분석 정보>\n"
          llm_response = financial_data.get("llm_response", "")
          if llm_response:
              part += f"{llm_response}\n\n"
          else:
              part += "재무 분석 결과가 없습니다.\n\n"
          part += "</사업보고서, 재무 분석 정보>\n"
          sources_info_parts.append(part)

      # Revenue Breakdown 데이터
      revenue_breakdown_data_str = agent_results.get("revenue_breakdown", {}).get("data", "")
      # create_all_section_content는 문자열로 기대하므로, 문자열인지 확인
      if revenue_breakdown_data_str and isinstance(revenue_breakdown_data_str, str) and len(revenue_breakdown_data_str.strip()) > 0:
          part = "------\n<매출 및 수주 현황>\n"
          part += f"{revenue_breakdown_data_str}\n\n"
          part += "</매출 및 수주 현황>\n"
          sources_info_parts.append(part)

      # Industry Analyzer 데이터
      industry_data_container = agent_results.get("industry_analyzer", {}).get("data", {})
      if industry_data_container and isinstance(industry_data_container, dict):
          part = "------\n<산업,섹터 분석>\n"
          analysis = industry_data_container.get("analysis", {})
          llm_response = analysis.get("llm_response", "")
          if llm_response:
              part += f"{llm_response}\n\n"
          else:
              searched_reports = industry_data_container.get("searched_reports", [])
              if searched_reports and isinstance(searched_reports, list) and searched_reports:
                  for report_item in searched_reports[:5]:
                      report_info = report_item.get("content", "")
                      report_source = report_item.get("source", "미상")
                      report_date = report_item.get("publish_date", "날짜 미상")
                      report_page = f"{report_item.get('page', '페이지 미상')} p"
                      part += f"[출처: {report_source}, {report_date}, {report_page}]\n{report_info}\n\n"
              else: # llm_response도 없고 searched_reports도 없을 경우
                  part += "산업 동향 분석 결과가 없습니다.\n\n" # create_all_section_content에는 이 부분이 명시적이지 않으나, 추가
          part += "</산업,섹터 분석>\n"
          sources_info_parts.append(part)

      # Confidential Analyzer 데이터
      confidential_data_container = agent_results.get("confidential_analyzer", {}).get("data", {})
      if confidential_data_container and isinstance(confidential_data_container, dict):
          part = "------\n<비공개자료>\n"
          analysis = confidential_data_container.get("analysis", {})
          llm_response = analysis.get("llm_response", "")
          if llm_response:
              part += f"{llm_response}\n\n"
          else:
              searched_reports = confidential_data_container.get("searched_reports", [])
              if searched_reports and isinstance(searched_reports, list) and searched_reports:
                  for report_item in searched_reports[:5]:
                      report_info = report_item.get("content", "")
                      report_source = report_item.get("source", "미상")
                      report_page = f"{report_item.get('page', '페이지 미상')} p" # 날짜 없음, create_all_section_content와 동일
                      part += f"[출처: {report_source}, {report_page}]\n{report_info}\n\n"
              else: # llm_response도 없고 searched_reports도 없을 경우
                  part += "비공개 자료 분석 결과가 없습니다.\n\n" # create_all_section_content에는 이 부분이 명시적이지 않으나, 추가
          part += "</비공개자료>\n"
          sources_info_parts.append(part)

      # Telegram Retriever 데이터
      telegram_data_list = agent_results.get("telegram_retriever", {}).get("data", [])
      if telegram_data_list and isinstance(telegram_data_list, dict):
          # format_telegram_messages는 RetrievedTelegramMessage 객체의 리스트를 기대할 수 있으나,
          # create_all_section_content는 telegram_data: Dict[str, Any]를 받음.
          # agent_results의 telegram_retriever 데이터가 메시지 문자열 리스트거나 객체 리스트일 수 있음.
          # format_telegram_messages 내부에서 이를 처리한다고 가정.
          # 지금은 create_all_section_content의 파라미터 타입(Dict)과 agent_results의 구조(List)가 불일치하여,
          # telegram_data_list (List)를 그대로 전달. format_telegram_messages가 이를 처리해야 함.
          formatted_msgs = format_telegram_messages(telegram_data_list, stock_code, stock_name)
          if formatted_msgs and formatted_msgs.strip(): # 메시지가 있을 경우에만 추가
              part = "------\n<내부DB>\n"
              part += f"{formatted_msgs}\n\n"
              part += "</내부DB>\n"
              sources_info_parts.append(part)

      # Web Search 데이터
      # create_all_section_content는 web_search_data.get("summary", "") 를 사용.
      # agent_results.get("web_search", {}).get("data", {}) 에서 "summary"를 찾음.
      web_search_main_data = agent_results.get("web_search", {}).get("data", {}) # 이 자체가 dict
      if web_search_main_data and isinstance(web_search_main_data, dict):
          web_search_summary = web_search_main_data.get("summary", "")
          if web_search_summary and web_search_summary.strip(): # 요약이 있을 경우에만 추가
              part = "------\n<웹 검색 결과>\n"
              part += f"{web_search_summary}\n\n"
              part += "</웹 검색 결과>\n"
              sources_info_parts.append(part)
      
      # Knowledge Integrator 데이터
      integrated_knowledge_data = agent_results.get("knowledge_integrator", {}).get("data", None) # 문자열 또는 None
      if integrated_knowledge_data and isinstance(integrated_knowledge_data, str) and integrated_knowledge_data.strip():
          part = "------\n<통합된 지식>\n"
          part += f"{integrated_knowledge_data}\n\n"
          part += "</통합된 지식>\n"
          sources_info_parts.append(part)

      if not sources_info_parts:
          return "추가 컨텍스트 정보 없음."
      
      return "\n".join(sources_info_parts).strip()

def create_section_prompt(query: str, stock_code: Optional[str], stock_name: Optional[str],
                classification: Dict[str, Any], telegram_data: Dict[str, Any],
                report_data: List[Dict[str, Any]], confidential_data: List[Dict[str, Any]],
                financial_data: Dict[str, Any],
                revenue_breakdown_data: str,
                industry_data: List[Dict[str, Any]], integrated_knowledge: Optional[Any],
                system_prompt: Optional[str] = None) -> ChatPromptTemplate:
        """요약을 위한 프롬프트 생성"""
        
        # 오늘 날짜 추가
        query_date = datetime.now().strftime("%Y-%m-%d")
        primary_intent = classification.get("primary_intent", "기타")
        complexity = classification.get("complexity", "중간")
        expected_answer_type = classification.get("expected_answer_type", "사실형")
        
        # 소스 정보 형식화
        sources_info = ""
        
        # 재무 정보
 
        if financial_data:
            sources_info += "------\n사업보고서, 재무 분석 정보:\n"
            llm_response = financial_data.get("llm_response", "")
            if llm_response:
                sources_info += f"{llm_response}\n\n"
            else:
                sources_info += "재무 분석 결과가 없습니다.\n\n"

        if revenue_breakdown_data and len(revenue_breakdown_data) > 0:
            sources_info += "------\n매출 및 수주 현황:\n"
            sources_info += f"{revenue_breakdown_data}\n\n"

        
        
        # 기업 리포트
        if report_data:
            analysis = report_data.get("analysis", {})
            sources_info += "------\n출처 - 기업 리포트:\n"
            if analysis:
                # 전체 소스를 다 줄게 아니라, 기업리포트 에이전트가 출력한 결과만 전달.
                # 아.. 인용처리가 애매해지네.
                # 일단은 기업리포트 결과만 남겨보자.
                sources_info += f" - 투자의견:\n{analysis.get('investment_opinions', '')}\n\n"
                sources_info += f" - 종합의견:\n{analysis.get('opinion_summary', '')}\n\n"
                sources_info += f" - 최종결과:\n{analysis.get('llm_response', '')}\n\n"
            else:
                searched_reports = report_data.get("searched_reports", [])
                for report in searched_reports[:5]:
                    report_info = report.get("content", "")
                    report_source = report.get("source", "미상")
                    report_date = report.get("publish_date", "날짜 미상")
                    report_page = f"{report.get('page', '페이지 미상')} p"
                    sources_info += f"[출처: {report_source}, {report_date}, {report_page}]\n{report_info}\n\n"

        # 산업 동향(일단 미구현. 산업리포트 에이전트 추가 후에 풀것)
        if industry_data:
            analysis = industry_data.get("analysis", {})
            sources_info += "------\n출처 - 산업 동향:\n"
            if analysis:
                sources_info += f" - 최종결과:\n{analysis.get('llm_response', '')}\n\n"
            else:
                searched_reports = industry_data.get("searched_reports", [])
                for report in searched_reports[:5]:
                    report_info = report.get("content", "")
                    report_source = report.get("source", "미상")
                    report_date = report.get("publish_date", "날짜 미상")
                    report_page = f"{report.get('page', '페이지 미상')} p"
                    sources_info += f"[출처: {report_source}, {report_date}, {report_page}]\n{report_info}\n\n"

         # 비공개 리포트
        if confidential_data:
            analysis = confidential_data.get("analysis", {})
            sources_info += "------\n출처 - 비공개자료:\n"
            if analysis:
                # 전체 소스를 다 줄게 아니라, 기업리포트 에이전트가 출력한 결과만 전달.
                # 아.. 인용처리가 애매해지네.
                # 일단은 기업리포트 결과만 남겨보자.
                sources_info += f" - 최종결과:\n{analysis.get('llm_response', '')}\n\n"
            else:
                searched_reports = confidential_data.get("searched_reports", [])
                for report in searched_reports[:5]:
                    report_info = report.get("content", "")
                    report_source = report.get("source", "미상")
                    report_page = f"{report.get('page', '페이지 미상')} p"
                    #sources_info += f"[출처: {report_source}, {report_date}, {report_page}]\n{report_info}\n\n"         
                    sources_info += f"[출처: {report_source}, {report_page}]\n{report_info}\n\n"         
        
        # 텔레그램 메시지
        if telegram_data:
            formatted_msgs = format_telegram_messages(telegram_data, stock_code, stock_name)
            sources_info += f"------\n출처 - 내부DB :\n{formatted_msgs}\n\n"
        
        

        
        # 통합된 지식
        if integrated_knowledge:
            sources_info += f"통합된 지식:\n{integrated_knowledge}\n\n"

        
        # 정보가 없는 경우
        if not sources_info:
            sources_info = "검색된 정보가 없습니다. 질문에 관련된 정보를 찾을 수 없습니다."
        
        # 시스템 메시지와 사용자 메시지 분리 구성
        if system_prompt:
            system_message = SystemMessagePromptTemplate.from_template(system_prompt)
        else:
            system_message = SystemMessagePromptTemplate.from_template(PROMPT_GENERATE_SECTION_CONTENT)
        user_message = HumanMessagePromptTemplate.from_template(DEEP_RESEARCH_USER_PROMPT)
        
        # ChatPromptTemplate 구성
        prompt = ChatPromptTemplate.from_messages([
            system_message,
            user_message
        ]).partial(
            query=query,
            query_date=query_date,
            stock_code=stock_code or "정보 없음",
            stock_name=stock_name or "정보 없음",
            primary_intent=primary_intent,
            complexity=complexity,
            expected_answer_type=expected_answer_type,
            sources_info=sources_info
        )
        return prompt
