import asyncio
from datetime import datetime
import os
import sys
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

# 한글 폰트 설정
plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False  # 마이너스 기호 깨짐 방지

# 프로젝트 루트 디렉토리를 Python 경로에 추가
project_root = str(Path(__file__).parent.parent)
sys.path.append(project_root)

from common.utils.util import dict_to_formatted_str
from stockeasy.services.telegram.question_classifier import QuestionClassifierService
from common.app import LoadEnvGlobal
from common.services.llm_models import LLMModels
from sklearn.metrics.pairwise import cosine_similarity

import logging

# 환경 변수 로드
LoadEnvGlobal()


# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
import asyncio
from common.services.embedding import EmbeddingService
from common.services.embedding_models import EmbeddingModelType

import asyncio
import numpy as np
import json
import matplotlib.pyplot as plt
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.metrics import precision_recall_curve, average_precision_score, f1_score, accuracy_score, confusion_matrix

# 임베딩 서비스 초기화
embedding_service = EmbeddingService()
#embedding_service.change_model(EmbeddingModelType.GOOGLE_EN)
#embedding_service.change_model(EmbeddingModelType.OPENAI_ADA_002)
#embedding_service.change_model(EmbeddingModelType.KAKAO_EMBEDDING)
#embedding_service.change_model(EmbeddingModelType.UPSTAGE)
embedding_service.change_model(EmbeddingModelType.BGE_M3)

# Test data
texts = [
    # 금융 & 투자 (1-10)
    "주식시장의 기본은 거래소에서 주식이 어떻게 거래되는지 이해하는 것입니다. 시가총액, 주가수익비율, 배당수익률이 핵심 개념입니다. 투자자들은 투자 결정을 할 때 기술적, 기본적 요소를 모두 분석해야 합니다.",
    "채권시장은 고정수익 투자 기회를 제공합니다. 국채, 회사채, 지방채는 각각 다른 위험-수익 프로필을 가집니다. 듀레이션과 수익률은 채권 투자자가 고려해야 할 중요한 지표입니다.",
    "외환시장은 24시간 전 세계적으로 운영되며, 통화쌍이 거래됩니다. 외환 트레이더들은 경제지표, 금리, 정치적 요인을 분석하여 거래 결정을 내립니다. 주요 통화쌍으로는 EUR/USD와 USD/JPY가 있습니다.",
    "파생상품 거래는 선물, 옵션, 스왑을 포함합니다. 이러한 금융상품들은 기초자산으로부터 가치가 파생되며, 투기와 헤지 목적으로 사용됩니다. 옵션 전략에는 콜, 풋, 복합 조합이 있습니다.",
    "자산배분 전략은 투자자의 포트폴리오 다각화를 돕습니다. 현대 포트폴리오 이론은 주어진 위험 수준에서 기대수익을 최대화하는 최적 포트폴리오를 제시합니다. 주식, 채권, 부동산, 원자재 등 다양한 자산군이 있습니다.",
    "기술적 분석은 가격 패턴과 시장 지표에 초점을 맞춥니다. 차트 패턴, 이동평균, 모멘텀 지표는 트레이더들이 매수/매도 시점을 파악하는데 도움을 줍니다. 거래량 분석은 가격 움직임을 추가로 확인하는 데 사용됩니다.",
    "기본적 분석은 기업 재무와 경제적 요인을 검토합니다. 분석가들은 재무제표, 산업 동향, 경쟁력을 분석하여 내재가치를 산정합니다. ROE, ROA, 이익률이 주요 지표입니다.",
    "계량 투자는 수학적 모델과 알고리즘을 활용합니다. 팩터 투자 전략은 가치, 모멘텀, 퀄리티와 같은 특정 특성을 목표로 합니다. 위험 관리에는 포지션 크기 조정과 상관관계 분석이 포함됩니다.",
    "ESG 투자는 환경, 사회, 지배구조 요소를 고려합니다. 지속가능 투자는 재무적 수익과 긍정적 영향을 동시에 추구하는 투자자들 사이에서 인기를 얻고 있습니다. 녹색채권과 임팩트 투자는 성장하는 분야입니다.",
    "암호화폐 시장은 블록체인 기술을 기반으로 운영됩니다. 비트코인, 이더리움 등 디지털 자산은 새로운 자산군을 대표합니다. DeFi 프로토콜은 전통적 중개자 없이 대출, 차입, 거래를 가능하게 합니다.",

    # 거시경제 (11-20)
    "인플레이션은 구매력과 투자수익에 영향을 미칩니다. 중앙은행은 물가안정을 위해 통화정책 수단을 사용합니다. 비용인상 인플레이션과 수요견인 인플레이션은 서로 다른 경제적 의미를 가집니다.",
    "경제성장은 GDP와 관련 지표로 측정됩니다. 생산성, 혁신, 인적자본이 성장에 영향을 미치는 요인입니다. 경기순환은 확장과 수축 단계로 구성됩니다.",
    "통화정책 결정은 금리와 통화공급에 영향을 미칩니다. 중앙은행은 공개시장조작과 지급준비율 등의 도구를 사용합니다. 포워드 가이던스는 시장 참여자들의 정책 예측을 돕습니다.",
    "재정정책은 정부지출과 과세 결정을 포함합니다. 재정적자와 국가부채 수준은 경제 안정성에 영향을 미칩니다. 자동안정화 장치는 경제 변동을 완화하는데 도움을 줍니다.",
    "국제무역 흐름은 비교우위를 반영합니다. 국제수지는 국제거래를 추적합니다. 무역협정과 관세는 글로벌 상거래 패턴에 영향을 미칩니다.",
    "노동시장 동향은 임금과 고용수준에 영향을 미칩니다. 구조적 실업과 경기적 실업은 서로 다른 원인과 해결책을 가집니다. 노동력 참여율은 인구통계에 따라 다양합니다.",
    "금융시장 통합은 글로벌 상호연결성을 증가시킵니다. 자본흐름은 환율과 자산가격에 영향을 미칩니다. 규제 프레임워크는 시장 안정성 유지를 목표로 합니다.",
    "경제지표는 정책과 투자 결정을 안내합니다. 선행, 동행, 후행 지표는 서로 다른 관점을 제공합니다. 계절조정은 기저 추세 파악에 도움을 줍니다.",
    "공급망 경제는 팬데믹 이후 중요성이 부각되었습니다. 적시생산 시스템은 회복력 과제에 직면해 있습니다. 지역 생산 네트워크가 재고려되고 있습니다.",
    "디지털 경제 전환은 전통적 산업에 영향을 미칩니다. 플랫폼 경제와 네트워크 효과는 새로운 비즈니스 모델을 창출합니다. 디지털 통화는 통화시스템을 재편할 수 있습니다.",

    # 기업재무 (21-30)
    "기업가치평가 방법에는 DCF와 배수분석이 포함됩니다. 잉여현금흐름 추정에는 신중한 가정이 필요합니다. 잔존가치는 전체 가치의 상당 부분을 차지합니다.",
    "자본구조 결정은 부채와 자본 조달의 균형을 맞춥니다. 상충이론은 세금혜택과 파산비용을 고려합니다. 자금조달순위이론은 자금조달 선호도를 제시합니다.",
    "인수합병은 시너지와 위험을 창출합니다. 실사 과정은 대상 기업을 평가합니다. 합병 후 통합이 거래의 성공을 결정합니다.",
    "운전자본 관리는 운영 효율성을 최적화합니다. 현금순환주기는 유동성 수요에 영향을 미칩니다. 재고관리는 비용과 재고부족 위험의 균형을 맞춥니다.",
    "위험관리 전략은 기업가치를 보호합니다. 헤지 프로그램은 금융상품을 활용합니다. 전사적 위험관리는 포괄적 접근방식을 취합니다.",
    "재무제표 분석은 기업 성과를 보여줍니다. 비율분석은 기업과 추세를 비교합니다. 현금흐름 분석은 발생주의 회계를 보완합니다.",
    "배당정책은 주주수익과 자금조달에 영향을 미칩니다. 배당성향은 분배 선호도를 반영합니다. 자사주 매입은 배당의 대안을 제공합니다.",
    "기업지배구조는 이해관계자 이익을 조정합니다. 이사회 구조와 구성이 중요합니다. 경영진 보상설계는 인센티브에 영향을 미칩니다.",
    "프로젝트 평가는 NPV와 IRR 지표를 사용합니다. 자본예산 결정은 자원을 배분합니다. 실물옵션은 전략적 유연성을 제공합니다.",
    "자본비용 추정은 투자 결정을 안내합니다. WACC 계산은 자금조달 비용을 결합합니다. 베타 추정치는 체계적 위험을 측정합니다.",

    # 기술 & 혁신 (31-40)
    "인공지능은 비즈니스 프로세스를 변화시킵니다. 머신러닝 모델은 의사결정을 개선합니다. 자연어처리는 새로운 응용을 가능하게 합니다.",
    "블록체인 기술은 신뢰 없는 거래를 가능하게 합니다. 스마트 계약은 합의를 자동화합니다. 분산원장은 투명성을 제공합니다.",
    "클라우드 컴퓨팅은 확장 가능한 인프라를 제공합니다. SaaS 비즈니스 모델이 소프트웨어를 지배합니다. 엣지 컴퓨팅은 지연 요구사항을 해결합니다.",
    "사물인터넷은 물리적 세계와 디지털 세계를 연결합니다. 센서 네트워크는 빅데이터를 생성합니다. 디바이스 보안이 과제입니다.",
    "5G 네트워크는 새로운 응용을 가능하게 합니다. 낮은 지연시간은 실시간 서비스를 지원합니다. 네트워크 슬라이싱은 맞춤화를 제공합니다.",
    "양자컴퓨팅은 계산 혁신을 약속합니다. 양자우위 시연은 잠재력을 보여줍니다. 오류 수정이 여전히 과제입니다.",
    "사이버보안은 디지털 자산을 보호합니다. 제로 트러스트 아키텍처가 채택되고 있습니다. 랜섬웨어 위협이 계속 진화합니다.",
    "가상현실과 증강현실은 몰입형 경험을 창출합니다. 혼합현실은 물리적 세계와 디지털 세계를 결합합니다. 메타버스 개념이 가능성을 확장합니다.",
    "로봇 자동화는 생산성을 향상시킵니다. 협동 로봇은 인간과 함께 작업합니다. 자율 시스템은 정교한 제어가 필요합니다.",
    "녹색기술은 지속가능성 과제를 해결합니다. 재생에너지 비용이 계속 하락합니다. 탄소포집 기술이 발전하고 있습니다.",

    # Healthcare & Biotech (41-50) - Last two categories in English
    "Gene editing advances with CRISPR technology. Precision medicine targets individual characteristics. Ethical considerations guide development.",
    "Drug discovery uses computational methods. Clinical trials evaluate safety and efficacy. Regulatory approval processes ensure safety.",
    "Telemedicine expands healthcare access. Remote monitoring enables home care. Digital health platforms integrate services.",
    "Medical imaging advances with AI assistance. Diagnostic accuracy improves with deep learning. Image processing speeds increase.",
    "Personalized medicine uses genetic information. Biomarkers guide treatment selection. Patient outcomes improve with targeting.",
    "Vaccine development accelerated recently. mRNA technology enables rapid adaptation. Distribution challenges affect access.",
    "Mental health technology provides new tools. Digital therapeutics show promise. Teletherapy increases accessibility.",
    "Medical devices incorporate smart features. Wearable technology monitors health. Implantable devices advance capabilities.",
    "Healthcare data analytics improve outcomes. Population health management expands. Privacy concerns require protection.",
    "Biotechnology startups attract investment. Innovation ecosystems develop globally. Commercialization pathways evolve."
]

related_queries = [
    # 금융 & 투자 (1-10)
    "주가수익비율은 주식 가치평가에 어떤 영향을 미치나요?",
    "채권 수익률에 영향을 미치는 요인은 무엇인가요?",
    "금리는 외환거래에 어떤 영향을 미치나요?",
    "기본적인 옵션 거래 전략은 무엇인가요?",
    "분산투자 포트폴리오는 어떻게 구성하나요?",
    "주요 기술적 분석 지표는 무엇인가요?",
    "기업 재무제표는 어떻게 분석하나요?",
    "퀀트 전략에서 팩터 투자란 무엇인가요?",
    "ESG 점수는 투자 결정에 어떤 영향을 미치나요?",
    "암호화폐 시장에서 DeFi의 역할은 무엇인가요?",

    # 거시경제 (11-20)
    "인플레이션은 투자수익에 어떤 영향을 미치나요?",
    "경제성장률을 결정하는 요인은 무엇인가요?",
    "중앙은행은 어떻게 통화정책을 실행하나요?",
    "정부지출이 미치는 영향은 무엇인가요?",
    "무역적자는 경제에 어떤 영향을 미치나요?",
    "구조적 실업의 원인은 무엇인가요?",
    "자본흐름은 시장에 어떤 영향을 미치나요?",
    "가장 중요한 경제지표는 무엇인가요?",
    "공급망 위험은 어떻게 관리하나요?",
    "디지털 전환의 영향은 무엇인가요?",

    # 기업재무 (21-30)
    "기업의 내재가치는 어떻게 계산하나요?",
    "최적 자본구조는 어떻게 결정되나요?",
    "인수합병 기회는 어떻게 평가하나요?",
    "운전자본 최적화란 무엇인가요?",
    "기업 위험관리는 어떻게 구현하나요?",
    "주요 재무제표 비율은 무엇인가요?",
    "배당정책은 어떻게 설정하나요?",
    "좋은 기업지배구조의 조건은 무엇인가요?",
    "투자 프로젝트는 어떻게 평가하나요?",
    "자본비용은 어떻게 추정하나요?",

    # 기술 & 혁신 (31-40)
    "AI는 비즈니스 프로세스를 어떻게 변화시키나요?",
    "블록체인의 활용 사례는 무엇인가요?",
    "클라우드 컴퓨팅은 어떻게 구현하나요?",
    "IoT의 응용분야는 무엇인가요?",
    "5G 네트워크의 이점은 무엇인가요?",
    "양자컴퓨팅은 어떻게 작동하나요?",
    "사이버보안은 어떻게 개선하나요?",
    "VR/AR의 미래는 어떻게 될까요?",
    "로봇은 산업을 어떻게 변화시키나요?",
    "녹색기술 혁신은 무엇이 있나요?",

    # Healthcare & Biotech (41-50) - Last two categories in English
    "How does CRISPR gene editing work?",
    "What is modern drug discovery process?",
    "How effective is telemedicine?",
    "How does AI help medical imaging?",
    "What is personalized medicine?",
    "How are vaccines developed?",
    "What are digital mental health tools?",
    "How smart are medical devices?",
    "How to use healthcare analytics?",
    "What drives biotech innovation?"
]

unrelated_queries = [
    # 금융 & 투자 (1-10)
    "초콜릿 쿠키는 어떻게 만드나요?",
    "축구 규칙은 무엇인가요?",
    "토마토는 어떻게 기르나요?",
    "재즈 음악의 역사는 무엇인가요?",
    "반려견 훈련은 어떻게 하나요?",
    "파리의 인기 관광지는 어디인가요?",
    "수제 파스타는 어떻게 만드나요?",
    "기본적인 사진 촬영 기법은 무엇인가요?",
    "명상은 어떻게 시작하나요?",
    "자동차 기본 관리 팁은 무엇인가요?",

    # 거시경제 (11-20)
    "정원 토양은 어떻게 개선하나요?",
    "효과적인 운동 루틴은 무엇인가요?",
    "수채화는 어떻게 그리나요?",
    "기본 뜨개질 패턴은 무엇인가요?",
    "초밥은 어떻게 만드나요?",
    "인기있는 보드게임은 무엇인가요?",
    "새로운 언어는 어떻게 배우나요?",
    "인테리어 디자인 원칙은 무엇인가요?",
    "소설은 어떻게 쓰나요?",
    "기본 목공 기술은 무엇인가요?",

    # 기업재무 (21-30)
    "결혼식은 어떻게 계획하나요?",
    "좋은 캠핑장소는 어디인가요?",
    "자전거는 어떻게 관리하나요?",
    "와인 시음 기초는 무엇인가요?",
    "조류 관찰은 어떻게 시작하나요?",
    "도예 기법은 무엇인가요?",
    "노래 실력은 어떻게 향상시키나요?",
    "기본 댄스 스텝은 무엇인가요?",
    "양봉은 어떻게 시작하나요?",
    "패션 디자인 기초는 무엇인가요?",

    # 기술 & 혁신 (31-40)
    "사워도우 빵은 어떻게 만드나요?",
    "초보자를 위한 요가 자세는 무엇인가요?",
    "꽃꽂이는 어떻게 하나요?",
    "체스 오프닝 무브는 무엇인가요?",
    "퇴비는 어떻게 만드나요?",
    "기본 마술 트릭은 무엇인가요?",
    "커피는 어떻게 내리나요?",
    "유화 기법은 무엇인가요?",
    "주얼리는 어떻게 만드나요?",
    "정원 가꾸기 계절은 언제인가요?",

    # Healthcare & Biotech (41-50) - Last two categories in English
    "How to play guitar chords?",
    "What are basic origami patterns?",
    "How to make candles?",
    "What are astronomy basics?",
    "How to start rock climbing?",
    "What are calligraphy techniques?",
    "How to make soap?",
    "What are pottery glazing methods?",
    "How to start stamp collecting?",
    "What are basic sailing skills?"
]

# 다국어 테스트 데이터
multilingual_text = "Climate change is one of the most pressing challenges facing our planet today. Rising global temperatures, extreme weather events, and melting ice caps are all signs of a changing climate."
multilingual_queries = {
    "ko": ["기후 변화의 주요 징후는 무엇인가요?", "지구 온난화의 영향은 무엇인가요?"],
    "en": ["What are the main signs of climate change?", "How does global warming affect our planet?"],
    #"ja": ["気候変動の主な兆候は何ですか？", "地球温暖化の影響は何ですか？"],
    #"zh": ["气候变化的主要迹象是什么？", "全球变暖如何影响我们的星球？"]
}

# 임베딩 생성 함수
def get_embedding(text):
    """텍스트에 대한 임베딩 벡터를 반환합니다."""
    if not text or not isinstance(text, str):
        raise ValueError(f"유효하지 않은 텍스트입니다: {text}")
    return embedding_service.create_single_embedding(text)

# 1. 기본 유사도 평가
def evaluate_basic_similarity(texts, related_queries, unrelated_queries):
    """기본 유사도 평가를 수행합니다."""
    results = []
    
    for i, text in enumerate(texts):
        if not isinstance(text, str) or not text.strip():
            print(f"경고: 텍스트 {i}가 비어있거나 유효하지 않습니다. 건너뜁니다.")
            continue
            
        try:
            text_embedding = get_embedding(text)
            
            # 관련 쿼리 유사도
            related_similarities = []
            current_related_query = related_queries[i]
            if isinstance(current_related_query, str) and current_related_query.strip():
                query_embedding = get_embedding(current_related_query)
                similarity = float(cosine_similarity([text_embedding], [query_embedding])[0][0])
                related_similarities.append(similarity)
            
            # 비관련 쿼리 유사도
            unrelated_similarities = []
            current_unrelated_query = unrelated_queries[i]
            if isinstance(current_unrelated_query, str) and current_unrelated_query.strip():
                query_embedding = get_embedding(current_unrelated_query)
                similarity = float(cosine_similarity([text_embedding], [query_embedding])[0][0])
                unrelated_similarities.append(similarity)
            
            if not related_similarities or not unrelated_similarities:
                print(f"경고: 텍스트 {i}의 쿼리가 비어있습니다. 건너뜁니다.")
                continue
            
            avg_related = float(np.mean(related_similarities))
            avg_unrelated = float(np.mean(unrelated_similarities))
            
            result = {
                "text_id": int(i),
                "text_preview": str(text[:50] + "..."),
                "related_query": str(current_related_query),
                "unrelated_query": str(current_unrelated_query),
                "related_similarities": [float(x) for x in related_similarities],
                "unrelated_similarities": [float(x) for x in unrelated_similarities],
                "avg_related_similarity": float(avg_related),
                "avg_unrelated_similarity": float(avg_unrelated),
                "difference": float(avg_related - avg_unrelated),
                "success": bool(avg_related > avg_unrelated)
            }
            
            results.append(result)
            
        except Exception as e:
            print(f"경고: 텍스트 {i} 처리 중 오류 발생: {str(e)}")
            continue
    
    if not results:
        raise ValueError("유효한 평가 결과가 없습니다.")
    
    # 전체 성공률과 평균 차이 계산
    success_rate = float(sum(1 for r in results if r["success"]) / len(results))
    avg_difference = float(np.mean([r["difference"] for r in results]))
    
    return {
        "success_rate": float(success_rate),
        "avg_difference": float(avg_difference),
        "detailed_results": results
    }

# 2. 정밀도-재현율 곡선 평가
def evaluate_precision_recall(texts, related_queries, unrelated_queries):
    """정밀도-재현율 곡선을 통한 평가를 수행합니다."""
    all_similarities = []
    all_labels = []
    
    for i, text in enumerate(texts):
        text_embedding = get_embedding(text)
        
        # 관련 쿼리 (레이블 1)
        current_related_query = related_queries[i]
        if isinstance(current_related_query, str) and current_related_query.strip():
            query_embedding = get_embedding(current_related_query)
            similarity = float(cosine_similarity([text_embedding], [query_embedding])[0][0])
            all_similarities.append(similarity)
            all_labels.append(1)
        
        # 비관련 쿼리 (레이블 0)
        current_unrelated_query = unrelated_queries[i]
        if isinstance(current_unrelated_query, str) and current_unrelated_query.strip():
            query_embedding = get_embedding(current_unrelated_query)
            similarity = float(cosine_similarity([text_embedding], [query_embedding])[0][0])
            all_similarities.append(similarity)
            all_labels.append(0)
    
    if not all_similarities or not all_labels:
        raise ValueError("유효한 유사도 결과가 없습니다.")
    
    # 정밀도-재현율 곡선 계산
    precision, recall, thresholds = precision_recall_curve(all_labels, all_similarities)
    avg_precision = average_precision_score(all_labels, all_similarities)
    
    # 모든 NumPy 배열을 Python 기본 타입으로 변환
    result = {
        "average_precision": float(avg_precision),
        "precision": [float(p) for p in precision],
        "recall": [float(r) for r in recall],
        "thresholds": [float(t) for t in thresholds] if len(thresholds) > 0 else []
    }
    
    # 그래프 생성 및 저장
    plt.figure(figsize=(10, 7))
    plt.plot(result["recall"], result["precision"], marker='.')
    plt.xlabel('재현율(Recall)')
    plt.ylabel('정밀도(Precision)')
    plt.title(f'정밀도-재현율 곡선 (AP={result["average_precision"]:.3f})')
    plt.grid(True)
    
    # 파일명에서 '/'를 '_'로 변경하고 현재 디렉토리에 저장
    safe_filename = embedding_service.current_model_config.name.replace('/', '_')
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), f'{safe_filename}_precision_recall_curve.png')
    plt.savefig(output_path)
    print(f"정밀도-재현율 곡선 이미지 저장 경로: {output_path}")
    
    return result

# 3. 검색 성능 평가
def evaluate_retrieval(texts, all_queries):
    """검색 성능을 평가합니다."""
    # 모든 텍스트의 임베딩 생성
    text_embeddings = [get_embedding(text) for text in texts if isinstance(text, str) and text.strip()]
    
    # 모든 쿼리와 관련 텍스트 인덱스 준비
    flat_queries = []
    query_to_text_map = {}  # 쿼리가 어떤 텍스트에 관련되는지 매핑
    
    for text_idx, query in enumerate(all_queries):
        if isinstance(query, str) and query.strip():
            flat_queries.append(query)
            query_to_text_map[query] = int(text_idx)  # 명시적으로 int로 변환
    
    # MRR 계산
    mrr_scores = []
    query_results = []
    
    for query in flat_queries:
        query_embedding = get_embedding(query)
        relevant_text_idx = int(query_to_text_map[query])  # 명시적으로 int로 변환
        
        # 모든 텍스트와의 유사도 계산
        similarities = []
        for text_embedding in text_embeddings:
            similarity = float(cosine_similarity([query_embedding], [text_embedding])[0][0])
            similarities.append(similarity)
        
        # 유사도 기준으로 텍스트 정렬
        ranked_indices = np.argsort(similarities)[::-1].tolist()  # NumPy 배열을 리스트로 변환
        
        # 관련 텍스트의 순위 찾기
        for rank, idx in enumerate(ranked_indices):
            if int(idx) == relevant_text_idx:  # 명시적으로 int로 변환
                mrr = float(1.0 / (rank + 1))  # 명시적으로 float로 변환
                mrr_scores.append(mrr)
                
                query_results.append({
                    "query": str(query),
                    "relevant_text_idx": int(relevant_text_idx),
                    "rank": int(rank + 1),
                    "mrr": float(mrr),
                    "similarities": [float(s) for s in similarities]  # 모든 유사도를 float로 변환
                })
                break
    
    if not mrr_scores:
        raise ValueError("유효한 MRR 점수가 없습니다.")
        
    mean_mrr = float(np.mean(mrr_scores))  # 명시적으로 float로 변환
    
    return {
        "mean_reciprocal_rank": float(mean_mrr),
        "query_results": query_results
    }

# 4. 임계값 기반 분류 평가
def evaluate_classification(texts, related_queries, unrelated_queries):
    """임계값 기반 분류 성능을 평가합니다."""
    all_similarities = []
    all_labels = []
    
    for i, text in enumerate(texts):
        if not isinstance(text, str) or not text.strip():
            continue
            
        text_embedding = get_embedding(text)
        
        # 관련 쿼리 (레이블 1)
        current_related_query = related_queries[i]
        if isinstance(current_related_query, str) and current_related_query.strip():
            query_embedding = get_embedding(current_related_query)
            similarity = float(cosine_similarity([text_embedding], [query_embedding])[0][0])
            all_similarities.append(similarity)
            all_labels.append(1)
        
        # 비관련 쿼리 (레이블 0)
        current_unrelated_query = unrelated_queries[i]
        if isinstance(current_unrelated_query, str) and current_unrelated_query.strip():
            query_embedding = get_embedding(current_unrelated_query)
            similarity = float(cosine_similarity([text_embedding], [query_embedding])[0][0])
            all_similarities.append(similarity)
            all_labels.append(0)
    
    if not all_similarities or not all_labels:
        raise ValueError("유효한 유사도 결과가 없습니다.")
    
    # 최적의 임계값 찾기
    best_f1 = 0.0
    best_threshold = 0.0
    best_accuracy = 0.0
    best_confusion_matrix = None
    
    for threshold in np.arange(0.1, 1.0, 0.01):
        predictions = [1 if s >= threshold else 0 for s in all_similarities]
        current_f1 = float(f1_score(all_labels, predictions))
        current_accuracy = float(accuracy_score(all_labels, predictions))
        
        if current_f1 > best_f1:
            best_f1 = float(current_f1)
            best_threshold = float(threshold)
            best_accuracy = float(current_accuracy)
            best_confusion_matrix = confusion_matrix(all_labels, predictions)
    
    result = {
        "optimal_threshold": float(best_threshold),
        "best_f1_score": float(best_f1),
        "accuracy": float(best_accuracy),
        "confusion_matrix": best_confusion_matrix.tolist() if best_confusion_matrix is not None else None,
        "all_similarities": [float(s) for s in all_similarities],
        "all_labels": [int(l) for l in all_labels]
    }
    
    return result

# 5. 다국어 성능 평가
def evaluate_multilingual():
    """다국어 성능을 평가합니다."""
    text_embedding = get_embedding(multilingual_text)
    results = {}
    
    for language, queries in multilingual_queries.items():
        language_similarities = []
        
        for query in queries:
            query_embedding = get_embedding(query)
            similarity = cosine_similarity([text_embedding], [query_embedding])[0][0]
            language_similarities.append(float(similarity))
        
        results[language] = {
            "queries": queries,
            "similarities": language_similarities,
            "avg_similarity": float(np.mean(language_similarities))
        }
    
    # 언어 간 평균 유사도 비교
    language_avg_similarities = {lang: data["avg_similarity"] for lang, data in results.items()}
    
    return {
        "detailed_results": results,
        "language_avg_similarities": language_avg_similarities,
        "overall_avg_similarity": float(np.mean([data["avg_similarity"] for data in results.values()]))
    }

# 6. 종합 평가 보고서 생성
async def generate_evaluation_report():
    """종합 평가 보고서를 생성합니다."""
    # 1. 기본 유사도 평가
    basic_similarity_results = evaluate_basic_similarity(texts, related_queries, unrelated_queries)
    
    # 2. 정밀도-재현율 곡선 평가
    precision_recall_results = evaluate_precision_recall(texts, related_queries, unrelated_queries)
    
    # 3. 검색 성능 평가
    retrieval_results = evaluate_retrieval(texts, related_queries)
    
    # 4. 임계값 기반 분류 평가
    classification_results = evaluate_classification(texts, related_queries, unrelated_queries)
    
    # 5. 다국어 성능 평가
    multilingual_results = evaluate_multilingual()
    
    # 현재 시간 가져오기
    current_time = await get_current_time()
    
    # 종합 보고서 생성
    report = {
        "basic_similarity_evaluation": basic_similarity_results,
        "precision_recall_evaluation": precision_recall_results,
        "retrieval_performance": retrieval_results,
        "classification_performance": classification_results,
        "multilingual_performance": multilingual_results,
        "model_info": {
            "model_name": embedding_service.current_model_config.name.replace('/', '_'),
            "dimension": embedding_service.current_model_config.dimension,
            "evaluation_date": current_time
        }
    }
    
    return report

async def get_current_time():
    """현재 시간을 문자열로 반환합니다."""
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# 7. 평가 결과 시각화
def visualize_results(report):
    """평가 결과를 시각화합니다."""
    # 1. 기본 유사도 시각화
    plt.figure(figsize=(12, 6))
    
    # 텍스트별 관련/비관련 쿼리 유사도 비교
    text_ids = [r["text_id"] for r in report["basic_similarity_evaluation"]["detailed_results"]]
    related_sims = [r["avg_related_similarity"] for r in report["basic_similarity_evaluation"]["detailed_results"]]
    unrelated_sims = [r["avg_unrelated_similarity"] for r in report["basic_similarity_evaluation"]["detailed_results"]]
    
    x = np.arange(len(text_ids))
    width = 0.35
    
    plt.bar(x - width/2, related_sims, width, label='관련 쿼리 유사도')
    plt.bar(x + width/2, unrelated_sims, width, label='비관련 쿼리 유사도')
    
    plt.xlabel('텍스트 ID')
    plt.ylabel('평균 유사도')
    plt.title('텍스트별 관련/비관련 쿼리 유사도 비교')
    plt.xticks(x, text_ids)
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    # 파일명에서 '/'를 '_'로 변경하고 현재 디렉토리에 저장
    safe_filename = embedding_service.current_model_config.name.replace('/', '_')
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), f'{safe_filename}_similarity_comparison.png')
    plt.savefig(output_path)
    print(f"유사도 비교 이미지 저장 경로: {output_path}")
    
    # 2. 다국어 성능 시각화
    plt.figure(figsize=(10, 6))
    
    languages = list(report["multilingual_performance"]["language_avg_similarities"].keys())
    avg_similarities = list(report["multilingual_performance"]["language_avg_similarities"].values())
    
    plt.bar(languages, avg_similarities, color='skyblue')
    plt.axhline(y=report["multilingual_performance"]["overall_avg_similarity"], color='r', linestyle='-', label='전체 평균')
    
    plt.xlabel('언어')
    plt.ylabel('평균 유사도')
    plt.title('언어별 평균 유사도 비교')
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    # 파일명에서 '/'를 '_'로 변경하고 현재 디렉토리에 저장
    safe_filename = embedding_service.current_model_config.name.replace('/', '_')
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), f'{safe_filename}_multilingual_comparison.png')
    plt.savefig(output_path)
    print(f"다국어 성능 이미지 저장 경로: {output_path}")
    
    # 3. 혼동 행렬 시각화
    if report["classification_performance"]["confusion_matrix"] is not None:
        plt.figure(figsize=(8, 6))
        cm = np.array(report["classification_performance"]["confusion_matrix"])
        
        plt.imshow(cm, interpolation='nearest', cmap=plt.cm.Blues)
        plt.title(f'혼동 행렬 (임계값: {report["classification_performance"]["optimal_threshold"]:.2f})')
        plt.colorbar()
        
        classes = ['비관련', '관련']
        tick_marks = np.arange(len(classes))
        plt.xticks(tick_marks, classes)
        plt.yticks(tick_marks, classes)
        
        # 행렬 내 숫자 표시
        thresh = cm.max() / 2.
        for i in range(cm.shape[0]):
            for j in range(cm.shape[1]):
                plt.text(j, i, format(cm[i, j], 'd'),
                        horizontalalignment="center",
                        color="white" if cm[i, j] > thresh else "black")
        
        plt.ylabel('실제 레이블')
        plt.xlabel('예측 레이블')
        plt.tight_layout()
        
        # 파일명에서 '/'를 '_'로 변경하고 현재 디렉토리에 저장
        safe_filename = embedding_service.current_model_config.name.replace('/', '_')
        output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), f'{safe_filename}_confusion_matrix.png')
        plt.savefig(output_path)
        print(f"혼동 행렬 이미지 저장 경로: {output_path}")

# NumPy 데이터 타입을 Python 기본 타입으로 변환하는 함수 추가
def convert_numpy_types(obj):
    """NumPy 데이터 타입을 Python 기본 데이터 타입으로 변환합니다."""
    if isinstance(obj, dict):
        return {key: convert_numpy_types(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_numpy_types(item) for item in obj]
    elif isinstance(obj, (np.int_, np.intc, np.intp, np.int8, np.int16, np.int32, np.int64,
                         np.uint8, np.uint16, np.uint32, np.uint64)):
        return int(obj)
    elif isinstance(obj, (np.float_, np.float16, np.float32, np.float64)):
        return float(obj)
    elif isinstance(obj, np.bool_):  # bool_ 타입 처리 수정
        return bool(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj

# 데이터 유효성 검사 함수
def validate_test_data():
    """테스트 데이터의 유효성을 검사합니다."""
    validation_results = {
        "is_valid": True,
        "errors": []
    }
    
    # 1. 기본 데이터 존재 여부 확인
    if not texts:
        validation_results["errors"].append("texts 리스트가 비어있습니다.")
        validation_results["is_valid"] = False
    
    if not related_queries:
        validation_results["errors"].append("related_queries 리스트가 비어있습니다.")
        validation_results["is_valid"] = False
    
    if not unrelated_queries:
        validation_results["errors"].append("unrelated_queries 리스트가 비어있습니다.")
        validation_results["is_valid"] = False
    
    # 2. 데이터 길이 일치 여부 확인
    if len(texts) != len(related_queries) or len(texts) != len(unrelated_queries):
        validation_results["errors"].append(
            f"데이터 길이가 일치하지 않습니다: texts({len(texts)}), "
            f"related_queries({len(related_queries)}), "
            f"unrelated_queries({len(unrelated_queries)})"
        )
        validation_results["is_valid"] = False
    
    # 3. 텍스트 데이터 유효성 검사
    for i, text in enumerate(texts):
        if not isinstance(text, str):
            validation_results["errors"].append(f"텍스트 {i}번이 문자열이 아닙니다: {type(text)}")
            validation_results["is_valid"] = False
        elif not text.strip():
            validation_results["errors"].append(f"텍스트 {i}번이 비어있습니다.")
            validation_results["is_valid"] = False
    
    # 4. 쿼리 데이터 유효성 검사
    for i, (related, unrelated) in enumerate(zip(related_queries, unrelated_queries)):
        if not isinstance(related, str):
            validation_results["errors"].append(f"관련 쿼리 {i}번이 문자열이 아닙니다: {type(related)}")
            validation_results["is_valid"] = False
        elif not related.strip():
            validation_results["errors"].append(f"관련 쿼리 {i}번이 비어있습니다.")
            validation_results["is_valid"] = False
            
        if not isinstance(unrelated, str):
            validation_results["errors"].append(f"비관련 쿼리 {i}번이 문자열이 아닙니다: {type(unrelated)}")
            validation_results["is_valid"] = False
        elif not unrelated.strip():
            validation_results["errors"].append(f"비관련 쿼리 {i}번이 비어있습니다.")
            validation_results["is_valid"] = False
    
    # 5. 다국어 데이터 유효성 검사
    if not multilingual_text or not isinstance(multilingual_text, str):
        validation_results["errors"].append("다국어 텍스트가 유효하지 않습니다.")
        validation_results["is_valid"] = False
    
    if not multilingual_queries or not isinstance(multilingual_queries, dict):
        validation_results["errors"].append("다국어 쿼리가 유효하지 않습니다.")
        validation_results["is_valid"] = False
    else:
        for lang, queries in multilingual_queries.items():
            if not isinstance(queries, list):
                validation_results["errors"].append(f"언어 {lang}의 쿼리가 리스트가 아닙니다.")
                validation_results["is_valid"] = False
            else:
                for i, query in enumerate(queries):
                    if not isinstance(query, str) or not query.strip():
                        validation_results["errors"].append(f"언어 {lang}의 쿼리 {i}번이 유효하지 않습니다.")
                        validation_results["is_valid"] = False
    
    return validation_results

# 메인 평가 함수 수정
async def test_evaluate_embeddings():
    """임베딩 모델 평가를 실행합니다."""
    print("임베딩 모델 평가를 시작합니다...")
    print(f"사용 모델: {embedding_service.current_model_config.name.replace('/', '_')}")
    
    # 데이터 유효성 검사 실행
    validation_results = validate_test_data()
    if not validation_results["is_valid"]:
        print("\n데이터 유효성 검사 실패:")
        for error in validation_results["errors"]:
            print(f"- {error}")
        raise ValueError("데이터 유효성 검사에 실패했습니다.")
    
    print("\n데이터 유효성 검사 완료")
    
    try:
        # 빠른 테스트 실행 (첫 번째 텍스트만)
        print("\n빠른 테스트 실행 중...")
        quick_result = quick_evaluate()
        print("빠른 테스트 결과:", json.dumps(quick_result, ensure_ascii=False, indent=2))
        
        # 전체 평가 실행
        print("\n전체 평가 시작...")
        report = await generate_evaluation_report()
        
        # NumPy 데이터 타입을 Python 기본 타입으로 변환
        report = convert_numpy_types(report)
        
        # 결과 저장
        output_file = f"{embedding_service.current_model_config.name.replace('/', '_')}_embedding_evaluation_report.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        # 결과 시각화
        visualize_results(report)
        
        print("\n평가가 완료되었습니다.")
        print(f"평가 결과 파일: {output_file}")
        print(f"성공률: {report['basic_similarity_evaluation']['success_rate']:.2f}")
        print(f"평균 차이: {report['basic_similarity_evaluation']['avg_difference']:.4f}")
        print(f"MRR: {report['retrieval_performance']['mean_reciprocal_rank']:.4f}")
        print(f"최적 임계값: {report['classification_performance']['optimal_threshold']:.4f}")
        print(f"F1 점수: {report['classification_performance']['best_f1_score']:.4f}")
        print(f"다국어 평균 유사도: {report['multilingual_performance']['overall_avg_similarity']:.4f}")
        
        return report
    except Exception as e:
        import traceback
        print("\n=== 상세 에러 정보 ===")
        print("에러 타입:", type(e).__name__)
        print("에러 메시지:", str(e))
        print("\n=== 스택 트레이스 ===")
        traceback.print_exc()
        print("\n=== 추가 디버그 정보 ===")
        print("현재 처리 중인 모델:", embedding_service.current_model_config.name.replace('/', '_'))
        raise

# 간단한 평가 함수 (빠른 테스트용)
def quick_evaluate():
    """빠른 테스트를 위한 간단한 평가를 수행합니다."""
    results = []
    
    for i, text in enumerate(texts[:2]):  # 처음 두 개의 텍스트만 평가
        text_embedding = get_embedding(text)
        
        # 관련 쿼리 유사도
        related_similarities = []
        current_related_query = related_queries[i]
        if isinstance(current_related_query, str) and current_related_query.strip():
            query_embedding = get_embedding(current_related_query)
            similarity = float(cosine_similarity([text_embedding], [query_embedding])[0][0])
            related_similarities.append(similarity)
        
        # 비관련 쿼리 유사도
        unrelated_similarities = []
        current_unrelated_query = unrelated_queries[i]
        if isinstance(current_unrelated_query, str) and current_unrelated_query.strip():
            query_embedding = get_embedding(current_unrelated_query)
            similarity = float(cosine_similarity([text_embedding], [query_embedding])[0][0])
            unrelated_similarities.append(similarity)
        
        if not related_similarities or not unrelated_similarities:
            print(f"경고: 텍스트 {i}의 쿼리가 비어있습니다. 건너뜁니다.")
            continue
            
        avg_related = float(np.mean(related_similarities))
        avg_unrelated = float(np.mean(unrelated_similarities))
        
        results.append({
            "text_id": int(i),
            "text_preview": str(text[:30] + "..."),
            "avg_related_similarity": float(avg_related),
            "avg_unrelated_similarity": float(avg_unrelated),
            "difference": float(avg_related - avg_unrelated),
            "success": bool(avg_related > avg_unrelated)  # bool_ 타입을 Python bool로 변환
        })
    
    return results

if __name__ == "__main__":
    try:
        # 전체 평가 실행
        asyncio.run(test_evaluate_embeddings())
    except KeyboardInterrupt:
        print("\n평가가 사용자에 의해 중단되었습니다.")
    except Exception as e:
        print(f"\n평가 중 오류 발생: {str(e)}")
    
    # 또는 빠른 테스트 실행
    # results = quick_evaluate()
    # print(json.dumps(results, indent=2, ensure_ascii=False))
