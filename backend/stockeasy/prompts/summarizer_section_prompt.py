from typing import Any, Dict, List, Optional

from langchain_core.prompts import ChatPromptTemplate

from stockeasy.prompts.telegram_prompts import format_telegram_messages

# --- START: 섹션별 종합 분석 프롬프트 정의 ---

PROMPT_GENERATE_SECTION_CONTENT = """
당신은 투자 리서치 보고서 전문 작성가입니다. 주어진 정보와 아래 원칙에 따라 요청된 섹션의 내용을 작성해야 합니다.

# 입력 정보
- 원래 질문: {query}
- 섹션 제목: {section_title}
- 섹션 설명: {section_description}
- 하위섹션 목록: {subsections_info}
- 분석 데이터:  
{all_analyses}

# 보고서 작성 7대 원칙

1.  **목적 집중:** 섹션의 목표와 설명에 부합하는 내용만 엄선하여 작성합니다.
2.  **데이터 기반:** 제공된 '분석 데이터' 내의 정보만을 근거로 서술하며, 없는 내용은 추측하지 않습니다.
3.  **전문가 톤앤매너:** 금융 투자 분야의 전문 용어를 활용해 신뢰도 높은 분석을 제공하며, 항상 존대말을 사용합니다.
4.  **논리적 인과관계:** 모든 분석은 '원인 → 현상 → 결과 → 시사점'의 흐름으로 명확하게 전개합니다.
5.  **시각적 강조:** 독자의 이해를 돕기 위해 **핵심 키워드나 수치는 굵게** 처리하고, 필요시 글머리 기호를 활용합니다.
6.  **재무 데이터 테이블화:** 모든 재무 지표는 아래 '테이블 출력 지침'에 따라 표로 만들어, 증감률(+/-)과 함께 제시합니다.
7.  **정리:** 각 섹션의 말미에는 핵심 내용을 3~5개로 요약한 **정리** 박스를 추가합니다.

# 테이블 출력 지침
- 테이블은 반드시 다음 형식에 맞춰 파이프(|) 사이에 공백 없이 작성합니다.
|항목|값1|값2|비고(선택적)|
|---|---|---|---|
|데이터1|내용1|내용2|설명1|

# 출처 표기 절대 원칙
- **목표:** 제공된 자료의 출처 정보를 바탕으로 정확한 출처를 표기해야 합니다. 이 규칙을 어기면 작업은 실패입니다.
- **가독성 우선:** 각 문장마다 출처 표기를 금지하고, 문단별로 통합하여 출처를 표기합니다.
- '데이터소스'는 출처로 표기하지 않습니다.
  **절대 금지**(오답):   --- 데이터소스: 산업섹터분석 --- => 임상 개발을 진행하고 있습니다(산업섹터분석).
  **필수 형식**(정답):   --- 데이터소스: 산업섹터분석 --- => 임상 개발을 진행하고 있습니다.

- **문단별 통합 출처 표기 방식:**
    1. 정보를 종합하여 자연스러운 문단을 작성 (출처 표기 없이)
    2. 문단 끝에 사용된 모든 출처를 한 번에 표기
    3. 같은 출처가 여러 번 사용되어도 문단당 한 번만 표기
    4. 형식: `(출처1, 날짜1; 출처2, 날짜2)`

- **변환 예시:**
    - **금지:** 매출 증가세입니다(KB, 2025-06-18). 영업이익도 상승했습니다(KB, 2025-06-18).
    - **정답:** 매출 증가세를 보였으며, 영업이익도 상승했습니다. (KB, 2025-06-18)

- **예외:** '데이터소스'가 내부DB, 비공개자료 인 경우에는 **절대 출처와 날짜를 표기하지 않고**, 본문에 자연스럽게 녹여 서술합니다.

이제 위의 모든 지침에 따라 "{section_title}" 섹션의 내용을 작성해주십시오.
"""
PROMPT_GENERATE_SECTION_CONTENT_OLD = """

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

# **테이블 출력 지침**
테이블은 반드시 다음 형식으로 작성하세요:

```
|항목|값1|값2|비고(선택적)|
|---|---|---|---|
|데이터1|내용1|내용2|설명1|
|데이터2|내용3|내용4|설명2|
```

- 파이프(|) 사이에 공백 없이 작성
- 헤더와 구분선(-) 사용 필수
- 정렬을 위한 추가 공백이나 탭 사용 금지

# 기본 작성 지침
1. **섹션 목적 집중**: 해당 섹션의 목적과 범위에 맞게 내용을 집중적으로 작성하세요.
2. **데이터 기반 분석**: 제공된 분석 데이터에서 해당 섹션과 관련된 정보를 선별하여 활용하세요.
3. **논리적 구성**: 섹션 내용을 논리적으로 구성하고, 필요한 경우 소제목을 활용하여 구조화하세요.
4. **전문성 표현**: 금융 및 투자 분야의 전문 용어를 적절히 활용하여 내용의 전문성을 높이세요.
5. **시각적 구조화**: 글머리 기호, 표, 중요 정보 강조 등을 활용하여 내용을 시각적으로 구조화하세요.
6. **항상 존대말투를 사용**하세요.


# 데이터 처리 및 표현 지침

## 출처 표기 지침
 ### 핵심 원칙
  - **가독성 최우선**: 각 문장마다 출처 표기를 절대 금지하고, 문단별로 통합하여 출처를 표기합니다
  - **문단별 통합 출처 표기**: 문단 끝에 사용된 모든 출처를 한 번에 표기합니다
  - **내부DB, 비공개자료는 절대 출처 표기하지 마세요**
  - **"내부DB", "비공개자료", "내부 자료" 등의 표현은 일체 사용 금지**

 ### 작업 순서
  1. 정보를 종합하여 자연스러운 문단을 작성 (출처 표기 없이)
  2. 문단 끝에 사용된 모든 출처를 한 번에 표기
  3. 같은 출처가 여러 번 사용되어도 문단당 한 번만 표기
  4. **내부DB나 비공개자료에서 가져온 정보는 출처 없이 자연스럽게 서술**

 ### 표기 형식
  - **통합 형식**: `(출처1, 날짜1; 출처2, 날짜2)`
  - 제공된 자료 출처 정보 기반으로 정확한 출처명 사용
  - **내부DB, 비공개자료 관련 출처는 어떤 형태로든 표기하지 마세요**
  

 ### 예시
 ❌ **금지:**
  - 수출데이터가 호조를 보이고 있습니다(내부DB)
  - 매출 증가세입니다(KB, 2025-06-18). 영업이익도 상승했습니다(KB, 2025-06-18).

  ✅ **정답:**
   수출데이터가 호조를 보이며, 매출 증가세를 보였고 영업이익도 상승했습니다. (KB, 2025-06-18; Hana, 2025-05-13)

 ### 중요한 주의사항
  - **내부DB나 비공개자료의 정보는 마치 일반적으로 알려진 사실처럼 자연스럽게 서술하세요**
  - **출처 표기는 오직 공개된 증권사 리포트, 사업보고서, 웹 검색 결과에만 적용하세요**

## 재무 데이터 표현
- 모든 재무 지표는 마크다운 테이블로 구조화하고, 매출액/영업이익/순이익을 하나의 테이블로 통합 분석하세요.
- 전년 대비(YoY), 전기 대비(QoQ) 변화율은 +/- 기호로 증감을 명확히 표시하세요.
- 금액 단위(억원, 조원)는 원본 데이터와 일치시키고, 큰 금액은 적절히 변환하세요(10,000억원=1조원).
- 재무 데이터 소스는 다음 우선순위로 사용: 사업보고서 > 기업리포트 > 내부DB > 비공개자료
- 실적 분석은 하위 목차 없이 하나의 통합된 분석으로 제시하세요.

## 심층 분석 방법
- **교차 검증**: 서로 다른 출처의 정보를 교차 검증하고, 상충되는 정보는 이유와 함께 설명하세요.
- **논리적 흐름**: 각 문단은 '원인→현상→결과→시사점' 구조로 작성하고, 인과관계를 명확히 하세요.
- **신뢰도 표시**: 확실한 정보("~임을 확인함")와 불확실한 정보("~로 추정됨")를 구분하여 표현하세요.
- **시각적 강조**: 핵심 문구와 중요 수치는 굵은 글씨로 강조하고, 계층적 정보는 글머리 기호로 구조화하세요.

## 자연스러운 보고서 구성
- **내용 요소 포함**: 현황, 분석, 시사점, 전망의 핵심 요소들을 포함하되, 경직된 하위 섹션으로 구분하지 마세요.
- **유기적 흐름**: 각 요소들이 자연스럽게 연결되어 흘러가는 하나의 완결된 보고서 형태로 작성하세요.
- **적절한 소제목**: 필요한 경우에만 자연스러운 소제목을 사용하고, 획일적인 "현황/분석/시사점/전망" 제목은 피하세요.
- **정량적 데이터와 정성적 분석을 균형 있게 통합**하여 읽기 편한 형태로 구성하세요.
- **각 섹션 끝에는 "정리" 박스를 추가**하여 주요 포인트를 3-5개 항목으로 정리하세요.
- **요청된 섹션의 내용만 작성**하고, 다른 섹션 내용은 포함하지 마세요.

이제 "{section_title}" 섹션의 내용을 작성해주세요.
"""

# --- START: 핵심 요약 생성 프롬프트 정의 ---
PROMPT_GENERATE_EXECUTIVE_SUMMARY = """
당신은 투자 리서치 보고서의 전문 분석가이자 통합적 사고를 가진 요약 전문가입니다.
이미 작성된 보고서의 각 섹션 내용을 바탕으로, 사용자의 질문에 대한 핵심 인사이트를 담은 '핵심 요약' 섹션을 작성해야 합니다.

# 작업 목표
아래 제공된 사용자 질문, 보고서 제목, 그리고 이미 생성된 보고서의 다른 섹션들 내용을 바탕으로, '핵심 요약' 섹션을 작성하세요.
각 섹션의 핵심 내용을 추출하고 연관관계를 정리하여, 사용자가 전체 보고서를 읽지 않고도 질문에 대한 통찰력 있는 답변을 얻을 수 있도록 합니다.

# 입력 정보
원본 사용자 질문: {original_query}
보고서 제목: {report_title}

<이미 생성된 보고서 섹션별 내용>
{sections_summary}
</이미 생성된 보고서 섹션별 내용>

# "핵심 요약" 섹션 작성 지침
1.  **질문 중심 접근**: 사용자의 원래 질문에 초점을 맞추어, 그 질문에 대한 명확한 답변을 제공하세요. 이 질문이 핵심 요약의 기준점입니다.

2.  **각 섹션의 핵심 요소 통합**:
    - 각 섹션의 가장 중요한 정보와 인사이트를 식별하세요
    - 이러한 요소들이 어떻게 사용자 질문과 관련되는지 명확히 하세요
    - 단순히 내용을 줄이는 것이 아니라, 각 섹션의 핵심 가치를 유지하세요

3.  **연관관계 분석**:
    - 다양한 섹션에서 발견된 정보 간의 연결점과 패턴을 찾으세요
    - 인과관계, 상호의존성, 상충점 또는 보완점을 강조하세요
    - "섹션 A의 기술 발전은 섹션 B의 시장 기회에 영향을 미치며..." 같은 방식으로 연결하세요

4.  **통찰력 있는 관점 제시**:
    - 단순 사실 나열을 넘어, 데이터와 정보가 시사하는 더 큰 의미를 제시하세요
    - "따라서..." "이는...를 의미합니다" "이러한 맥락에서..." 같은 표현으로 통찰력을 드러내세요
    - 다양한 데이터 포인트를 종합하여 새로운 시각을 제공하세요

5.  **명확한 구조화**:
    - 핵심 요약은 5-6개의 핵심 포인트로 구성하는 것이 이상적입니다
    - 각 포인트는 간결한 제목과 2-3문장의 설명으로 구성하세요
    - 글머리 기호(•)을 적절히 활용하여 가독성을 높이세요
    - 기울임체나 굵은 글씨를 사용하여 핵심 용어나 중요 결론을 강조하세요

6.  **이해하기 쉬운 언어**:
    - 복잡한 개념을 명확하고 접근하기 쉬운 방식으로 설명하세요
    - 필요한 전문 용어는 유지하되, 가능한 간결하고 직관적인 표현을 사용하세요

7.  **균형 잡힌 관점**:
    - 긍정적 측면과 도전/리스크 요소를 균형 있게 다루세요
    - 확실한 정보와 가능성 있는 추측을 명확히 구분하세요
    - 다양한 관점이나 해석이 있다면 간략히 언급하세요

8.  **실행 가능한 인사이트**:
    - 요약은 독자가 "그래서 어떻게 해야 하는가?"라는 질문에 답할 수 있어야 합니다
    - 주요 발견이 투자자, 기업 또는 관련 이해관계자에게 갖는 실질적 의미를 언급하세요
    - 적절한 경우, 향후 모니터링이 필요한 주요 지표나 이벤트를 제안하세요

9.  **출력 형식**: 
    - 보고서 형태로 작성하되, 하위 목차는 생성하지 않습니다
    - 글머리 기호(•)을 적절히 활용하여 핵심 포인트를 구분하세요. 숫자 목록은 사용하지 않습니다.
    - 1-2개 문단의 일반적 개요로 시작한 후, 5-6개의 주요 포인트를 구조화하여 제시하세요

10. **출처 표기 지침 (핵심 요약)**:
    - **핵심 요약 섹션은 출처 표기를 하지 않습니다**
    - **가독성 최우선:** 핵심 요약은 독자가 빠르게 핵심 내용을 파악할 수 있도록 하는 것이 목적이므로, 출처 표기 없이 깔끔하게 작성하세요
    - **자연스러운 서술:** 모든 정보는 마치 일반적으로 알려진 사실처럼 자연스럽게 서술하세요
    - **출처 언급 금지:** 어떠한 형태의 출처도 언급하지 마세요 (증권사 리포트, 사업보고서, 웹 검색 결과, 내부DB, 비공개자료 등 모든 출처 표기 금지)
    - **"내부DB", "비공개자료", "내부 자료", "(출처명, 날짜)" 등의 표현은 일체 사용 금지**

이제 "{section_title}" 섹션의 내용을 작성해주세요. 이 섹션은 보고서의 가장 첫 부분에 위치하여 독자에게 질문에 대한 통찰력 있는 답변과 전체 보고서의 핵심 가치를 제공합니다.
"""
# --- END: 핵심 요약 생성 프롬프트 정의 ---


PROMPT_GENERATE_TECHNICAL_ANALYSIS_SECTION = """
당신은 기술적 분석 전문가이자 투자 리서치 보고서 작성가입니다. 주어진 기술적 분석 데이터를 바탕으로 해당 섹션의 내용을 작성해야 합니다.

# 작업 목표
아래 제공된 기술적 분석 데이터를 바탕으로 투자 리서치 보고서의 기술적 분석 섹션 내용을 전문적으로 작성하세요.

# 입력 정보
원래 질문: {query}

섹션 제목: {section_title}
섹션 설명: {section_description}
하위섹션 목록: {subsections_info}

<기술적 분석 데이터>
{all_analyses}
{price_chart}
</기술적 분석 데이터>

# **차트 플레이스홀더 삽입 지침**
기술적 분석 섹션에서는 차트 분석을 위한 차트 플레이스홀더를 **반드시** 삽입해야 합니다:

1. **차트 플레이스홀더 타입**: 차트 분석이 필요한 위치에 다음 형식의 플레이스홀더를 삽입하세요:
   - 주가 차트: `[CHART_PLACEHOLDER:PRICE_CHART]`
   - 추세추종 지표 차트: `[CHART_PLACEHOLDER:TREND_FOLLOWING_CHART]`
   - 모멘텀 지표 차트: `[CHART_PLACEHOLDER:MOMENTUM_CHART]`

2. **플레이스홀더 배치 위치**:
   - 차트 패턴 분석 설명 직후
   - 각 지표 유형별 분석 설명과 함께
   - 지지선/저항선 분석 설명과 함께

3. **플레이스홀더 선택 기준**:
   - **추세추종 지표 분석**: ADX, ADR, SuperTrend 등 추세 관련 내용이면 `[CHART_PLACEHOLDER:TREND_FOLLOWING_CHART]` 사용
   - **모멘텀 지표 분석**: RSI, MACD, 스토캐스틱 등 모멘텀 관련 내용이면 `[CHART_PLACEHOLDER:MOMENTUM_CHART]` 사용
   - **주가 및 지지/저항선 분석**: 주가 차트 및 지지,저항선 분석이면 `[CHART_PLACEHOLDER:PRICE_CHART]` 사용

4. **플레이스홀더 주변 맥락**:
   - 플레이스홀더 전에는 차트에서 보여줄 내용에 대한 간단한 설명을 제공하세요
   - 플레이스홀더 후에는 차트 분석 결과와 해석을 제공하세요

예시:
```
현재 주가는 상승 추세를 보이고 있으며, 주요 지지선과 저항선이 형성되어 있습니다.

[CHART_PLACEHOLDER:PRICE_CHART]

위 차트에서 확인할 수 있듯이, 주가는 470,500원과 432,000원에서 강한 지지를 받고 있으며...

추세추종 지표들(ADX, SuperTrend 등)을 종합적으로 분석해보겠습니다.

[CHART_PLACEHOLDER:TREND_FOLLOWING_CHART]

모멘텀 지표들(RSI, MACD 등)을 통해 현재 매수/매도 타이밍을 분석해보겠습니다.

[CHART_PLACEHOLDER:MOMENTUM_CHART]
```

# **테이블 출력 지침**
테이블은 반드시 다음 형식으로 작성하세요:

```
|항목|값|비고|
|---|---|---|
|데이터1|내용1|설명1|
|데이터2|내용2|설명2|
```

- 파이프(|) 사이에 공백 없이 작성
- 헤더와 구분선(-) 사용 필수
- 정렬을 위한 추가 공백이나 탭 사용 금지
- **주의**: 최근 주가 동향(일별/주별 주가 변동) 관련 테이블은 생성하지 마세요

# **출처 표기 지침 (기술적 분석)**
- **가독성 우선:** 각 문장마다 출처 표기를 금지하고, 문단별로 통합하여 출처를 표기하세요
- **문단별 통합 방식:** 정보를 종합하여 자연스러운 문단을 작성한 후, 문단 끝에 사용된 모든 출처를 한 번에 표기하세요
- **출처 형식:** `(출처1, 날짜1; 출처2, 날짜2)` 형태로 표기하세요
- **내부DB, 비공개자료, 차트데이터에서 가져온 정보는 절대 출처를 표기하지 마세요**
- **"내부DB", "비공개자료", "내부 자료", "차트데이터" 등의 표현은 일체 사용 금지**
- 기술적 분석에 사용된 차트 데이터나 지표 데이터는 자연스럽게 서술하고 출처 표기하지 마세요
- 오직 공개된 증권사 리포트나 외부 자료에서 가져온 정보만 출처 표기하세요

# **주가, 거래량, 수급 분석** 섹션 분석 지침:
   - 참고데이터: 수급(투자주체별 거래현황), 차트ohlcv(<차트데이터>)
   - <차트데이터> 항목의 일봉 차트데이터를 읽어서 분석하고, 투자추별 거래현황을 통해 수급을 분석하고, '주가, 거래량, 수급 분석' 섹션을 작성한다.
   - **최근 1개월 주가 움직임 우선 분석**: 최근 1개월간의 주가 변동을 거래량과 연계하여 집중 분석
   - **거래량 중심 추세 분석**: 주가 상승/하락 시 거래량 패턴과 특징을 통한 추세 강도 판단
   - **미래 추세 전망**: 거래량 패턴을 바탕으로 향후 주가 움직임과 예상 시나리오 제시
   - **금지**: 주가, 거래량 데이터를 테이블로 출력할 필요는 없음.

# 기술적 분석 작성 지침
1. **데이터 기반 분석**: 제공된 기술적 분석 데이터에서 핵심 정보를 선별하여 활용하세요.
2. **차트 패턴 분석**: 주가 추세, 지지선/저항선, 패턴 등을 명확히 설명하세요.
3. **지표 유형별 특성 설명**: 분석 시작 부분에 다음 내용을 반드시 포함하여 사용자에게 지표의 특성을 명확히 설명하세요.
   - **추세추종 지표와 모멘텀 지표의 차이점과 특성**
   - **각 지표 유형이 제공하는 신호의 의미와 한계**
   - **두 지표 유형이 상충할 때의 해석 방법**
   - **본 분석에서 추세추종 지표를 주축으로 사용하는 이유**
   
4. **핵심 기술적 지표 해석**: 다음 지표들을 중점적으로 분석하고 해석하세요.
   **추세추종 지표 (Main 지표)**:
   - 과열권을 판단할 수 있는 지표의 점수는 분석하여 결과를 제시할 것
   - **ADX (Average Directional Index)**: 추세 강도 측정 및 +DI/-DI를 통한 방향성 분석
   - **SuperTrend**: 추세 추종 지표를 통한 매수/매도 신호 분석
   - **ADR (Average Daily Range)**: 일중 평균 변동폭을 통한 변동성 분석
   - **RS(상대강도)**: 상대강도 지표를 통한 추세 강도 분석
     : RS - 기본 12개월 단위
     : RS_1M - 1개월 단위의 상대강도
     : RS_6M - 6개월 단위의 상대강도
     : 예제1) RS가 높고, RS_1M이 낮다면 = 12개월간 크게 상승했으나, 최근 1개월간 시세는 주춤
     : 예제2) RS가 낮고, RS_1M가 높다면 = 장기간 시세가 나지 않았으나, 최근 강한 상승
   
   **모멘텀 지표**:
   - **RSI (Relative Strength Index)**: 과매수/과매도 상태 및 매매 신호 분석
     : 85점 이상이면 극도의 과한 추세로, 보유자의 영역 혹은 보유중이면 비중 축소를 적극 어필
   - **MACD**: 이동평균선 수렴확산을 통한 모멘텀 변화 분석
   - **스토캐스틱**: 단기 모멘텀 및 과매수/과매도 신호 분석
   - **기타 지표**: 볼린저 밴드 등 추가 지표가 있다면 함께 분석
   
   **지표 유형별 특성**:
   - **추세추종 지표**: 추세가 발생한 후 이를 따라가는 특성으로, 추세 지속성을 중시하며 늦은 진입이지만 안정적인 신호 제공
   - **모멘텀 지표**: 가격 변화의 속도와 강도를 측정하여 추세 전환을 빠르게 포착하지만, 잦은 거짓 신호 발생 가능
   - **상호 관계**: 추세추종 지표와 모멘텀 지표는 서로 반대되는 특성을 가지며, 추세추종 지표가 상승 신호일 때 모멘텀 지표는 과매수를 나타낼 수 있음
5. **종합 분석 섹션** 작성 지침:
   - 매매 전략은 작성하지 않습니다.
   - 매수가/매도가/손절가 등 매매와 직접적으로 관계되는 언급은 절대로 작성하면 안됩니다.

6. **지표 간 상관관계 및 종합 분석**: 
   - 추세추종 지표 주축으로 모멘텀 지표는 보조 확인 도구 활용
   - 지표 간 일치/상충 시 종합 판단 및 **향후 예상 추세 적극 제시**
7. **매매 신호 및 실전 적용**: 진입/청산 전략, 손절가/목표가 등 구체적 정보 제공
8. **수급 분석**: 투자주체별 매매 동향과 기술적 분석 연계
9. **리스크 및 주의사항**: 과매수/과매도, 변동성, 추세 전환 가능성 명시
10. **시각적 구조화 및 존대말투 사용**: 소제목, 표, 글머리 기호 활용하여 체계적 구성

이제 "{section_title}" 섹션의 내용을 작성해주세요.
"""


def create_all_section_content(
    stock_code: Optional[str],
    stock_name: Optional[str],
    telegram_data: Dict[str, Any],
    report_data: List[Dict[str, Any]],
    confidential_data: List[Dict[str, Any]],
    financial_data: Dict[str, Any],
    revenue_breakdown_data: str,
    industry_data: List[Dict[str, Any]],
    integrated_knowledge: Optional[Any],
    web_search_data: List[Dict[str, Any]],
) -> ChatPromptTemplate:
    """요약을 위한 프롬프트 생성"""

    # 소스 정보 형식화
    sources_info = ""

    # 재무 정보

    if financial_data:
        sources_info += "--- 데이터소스: 사업보고서 재무분석 ---\n\n"
        llm_response = financial_data.get("llm_response", "")
        if llm_response:
            sources_info += f"### 분석결과\n- **내용**: {llm_response}\n\n"
        else:
            sources_info += "### 분석결과\n- **내용**: 재무 분석 결과가 없습니다.\n\n"

    if revenue_breakdown_data and len(revenue_breakdown_data) > 0:
        sources_info += "--- 데이터소스: 매출수주현황 ---\n\n"
        sources_info += f"### 현황분석\n- **내용**: {revenue_breakdown_data}\n\n"

    # 기업 리포트
    if report_data:
        analysis = report_data.get("analysis", {})
        sources_info += "--- 데이터소스: 기업리포트 ---\n\n"
        if analysis:
            # 전체 소스를 다 줄게 아니라, 기업리포트 에이전트가 출력한 결과만 전달.
            # 아.. 인용처리가 애매해지네.
            # 일단은 기업리포트 결과만 남겨보자.
            sources_info += f"### 투자의견\n- **내용**: {analysis.get('investment_opinions', '')}\n\n"
            sources_info += f"### 종합의견\n- **내용**: {analysis.get('opinion_summary', '')}\n\n"
            sources_info += f"### 최종결과\n- **내용**: {analysis.get('llm_response', '')}\n\n"
        else:
            searched_reports = report_data.get("searched_reports", [])
            for i, report in enumerate(searched_reports[:5]):
                report_info = report.get("content", "")
                report_source = report.get("source", "미상")
                report_date = report.get("publish_date", "날짜 미상")
                report_page = f"{report.get('page', '페이지 미상')} p"
                sources_info += f"### 자료 {i + 1}\n"
                sources_info += f"- **출처**: {report_source}\n"
                sources_info += f"- **날짜**: {report_date}\n"
                sources_info += f"- **페이지**: {report_page}\n"
                sources_info += f"- **내용**: {report_info}\n\n"

    # 산업 동향(일단 미구현. 산업리포트 에이전트 추가 후에 풀것)
    if industry_data:
        analysis = industry_data.get("analysis", {})
        sources_info += "--- 데이터소스: 산업섹터분석 ---\n\n"
        if analysis:
            sources_info += f"### 최종결과\n- **내용**: {analysis.get('llm_response', '')}\n\n"
        else:
            searched_reports = industry_data.get("searched_reports", [])
            for i, report in enumerate(searched_reports[:5]):
                report_info = report.get("content", "")
                report_source = report.get("source", "미상")
                report_date = report.get("publish_date", "날짜 미상")
                report_page = f"{report.get('page', '페이지 미상')} p"
                sources_info += f"### 자료 {i + 1}\n"
                sources_info += f"- **출처**: {report_source}\n"
                sources_info += f"- **날짜**: {report_date}\n"
                sources_info += f"- **페이지**: {report_page}\n"
                sources_info += f"- **내용**: {report_info}\n\n"

    # 비공개 리포트
    if confidential_data:
        analysis = confidential_data.get("analysis", {})
        sources_info += "--- 데이터소스: 비공개자료 ---\n\n"
        if analysis:
            # 전체 소스를 다 줄게 아니라, 기업리포트 에이전트가 출력한 결과만 전달.
            # 아.. 인용처리가 애매해지네.
            # 일단은 기업리포트 결과만 남겨보자.
            sources_info += f"### 최종결과\n- **내용**: {analysis.get('llm_response', '')}\n\n"
        else:
            searched_reports = confidential_data.get("searched_reports", [])
            for i, report in enumerate(searched_reports[:5]):
                report_info = report.get("content", "")
                report_source = report.get("source", "미상")
                report_page = f"{report.get('page', '페이지 미상')} p"
                sources_info += f"### 자료 {i + 1}\n"
                sources_info += f"- **출처**: {report_source}\n"
                sources_info += f"- **페이지**: {report_page}\n"
                sources_info += f"- **내용**: {report_info}\n\n"

    # 텔레그램 메시지
    if telegram_data:
        formatted_msgs = format_telegram_messages(telegram_data, stock_code, stock_name)
        sources_info += "--- 데이터소스: 내부DB ---\n\n"
        sources_info += f"### 메시지내용\n- **내용**: {formatted_msgs}\n\n"

    if web_search_data:
        web_search_summary = web_search_data.get("summary", "")
        sources_info += "--- 데이터소스: 웹검색결과 ---\n\n"
        sources_info += f"### 검색요약\n- **내용**: {web_search_summary}\n\n"

    # 통합된 지식
    if integrated_knowledge:
        sources_info += "--- 데이터소스: 통합지식 ---\n\n"
        sources_info += f"### 통합결과\n- **내용**: {integrated_knowledge}\n\n"

    # 정보가 없는 경우
    if not sources_info:
        sources_info = "검색된 정보가 없습니다. 질문에 관련된 정보를 찾을 수 없습니다."

    return sources_info


def format_other_agent_data(agent_results: Dict[str, Any], stock_code: Optional[str] = None, stock_name: Optional[str] = None) -> str:
    """
    다른 에이전트들의 결과 데이터를 create_all_section_content 함수와 유사한 형태로 포맷합니다.
    report_analyzer 데이터는 제외합니다.
    """
    sources_info_parts = []

    # Financial Analyzer 데이터
    financial_data = agent_results.get("financial_analyzer", {}).get("data", {})
    if financial_data:
        part = "--- 데이터소스: 사업보고서 재무분석 ---\n\n"
        llm_response = financial_data.get("llm_response", "")
        if llm_response:
            part += f"### 분석결과\n- **내용**: {llm_response}\n\n"
        else:
            part += "### 분석결과\n- **내용**: 재무 분석 결과가 없습니다.\n\n"
        sources_info_parts.append(part)

    # Revenue Breakdown 데이터
    revenue_breakdown_data_str = agent_results.get("revenue_breakdown", {}).get("data", "")
    # create_all_section_content는 문자열로 기대하므로, 문자열인지 확인
    if revenue_breakdown_data_str and isinstance(revenue_breakdown_data_str, str) and len(revenue_breakdown_data_str.strip()) > 0:
        part = "--- 데이터소스: 매출수주현황 ---\n\n"
        part += f"### 현황분석\n- **내용**: {revenue_breakdown_data_str}\n\n"
        sources_info_parts.append(part)

    # Industry Analyzer 데이터
    industry_data_container = agent_results.get("industry_analyzer", {}).get("data", {})
    if industry_data_container and isinstance(industry_data_container, dict):
        part = "--- 데이터소스: 산업섹터분석 ---\n\n"
        analysis = industry_data_container.get("analysis", {})
        llm_response = analysis.get("llm_response", "")
        if llm_response:
            part += f"### 분석결과\n- **내용**: {llm_response}\n\n"
        else:
            searched_reports = industry_data_container.get("searched_reports", [])
            if searched_reports and isinstance(searched_reports, list) and searched_reports:
                for i, report_item in enumerate(searched_reports[:5]):
                    report_info = report_item.get("content", "")
                    report_source = report_item.get("source", "미상")
                    report_date = report_item.get("publish_date", "날짜 미상")
                    report_page = f"{report_item.get('page', '페이지 미상')} p"
                    part += f"### 자료 {i + 1}\n"
                    part += f"- **출처**: {report_source}\n"
                    part += f"- **날짜**: {report_date}\n"
                    part += f"- **페이지**: {report_page}\n"
                    part += f"- **내용**: {report_info}\n\n"
            else:  # llm_response도 없고 searched_reports도 없을 경우
                part += "### 분석결과\n- **내용**: 산업 동향 분석 결과가 없습니다.\n\n"
        sources_info_parts.append(part)

    # Confidential Analyzer 데이터
    confidential_data_container = agent_results.get("confidential_analyzer", {}).get("data", {})
    if confidential_data_container and isinstance(confidential_data_container, dict):
        part = "--- 데이터소스: 비공개자료 ---\n\n"
        analysis = confidential_data_container.get("analysis", {})
        llm_response = analysis.get("llm_response", "")
        if llm_response:
            part += f"### 분석결과\n- **내용**: {llm_response}\n\n"
        else:
            searched_reports = confidential_data_container.get("searched_reports", [])
            if searched_reports and isinstance(searched_reports, list) and searched_reports:
                for i, report_item in enumerate(searched_reports[:5]):
                    report_info = report_item.get("content", "")
                    report_source = report_item.get("source", "미상")
                    report_page = f"{report_item.get('page', '페이지 미상')} p"  # 날짜 없음, create_all_section_content와 동일
                    part += f"### 자료 {i + 1}\n"
                    part += f"- **출처**: {report_source}\n"
                    part += f"- **페이지**: {report_page}\n"
                    part += f"- **내용**: {report_info}\n\n"
            else:  # llm_response도 없고 searched_reports도 없을 경우
                part += "### 분석결과\n- **내용**: 비공개 자료 분석 결과가 없습니다.\n\n"
        sources_info_parts.append(part)

    # Telegram Retriever 데이터
    #   telegram_data_list = agent_results.get("telegram_retriever", {}).get("data", [])
    #   if telegram_data_list and isinstance(telegram_data_list, dict):
    #       formatted_msgs = format_telegram_messages(telegram_data_list, stock_code, stock_name)
    #       if formatted_msgs and formatted_msgs.strip(): # 메시지가 있을 경우에만 추가
    #           part = "------\n<내부DB>\n"
    #           part += f"{formatted_msgs}\n\n"
    #           part += "</내부DB>\n"
    #           sources_info_parts.append(part)

    # Web Search 데이터
    # create_all_section_content는 web_search_data.get("summary", "") 를 사용.
    # agent_results.get("web_search", {}).get("data", {}) 에서 "summary"를 찾음.
    web_search_main_data = agent_results.get("web_search", {}).get("data", {})  # 이 자체가 dict
    if web_search_main_data and isinstance(web_search_main_data, dict):
        web_search_summary = web_search_main_data.get("summary", "")
        if web_search_summary and web_search_summary.strip():  # 요약이 있을 경우에만 추가
            part = "--- 데이터소스: 웹검색결과 ---\n\n"
            part += f"### 검색요약\n- **내용**: {web_search_summary}\n\n"
            sources_info_parts.append(part)

    # Knowledge Integrator 데이터
    integrated_knowledge_data = agent_results.get("knowledge_integrator", {}).get("data", None)  # 문자열 또는 None
    if integrated_knowledge_data and isinstance(integrated_knowledge_data, str) and integrated_knowledge_data.strip():
        part = "--- 데이터소스: 통합지식 ---\n\n"
        part += f"### 통합결과\n- **내용**: {integrated_knowledge_data}\n\n"
        sources_info_parts.append(part)

    if not sources_info_parts:
        return "추가 컨텍스트 정보 없음."

    return "\n".join(sources_info_parts).strip()
