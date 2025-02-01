"""탤래그램 FastAPI 애플리케이션

이 모듈은 주식 관련 서비스를 위한 FastAPI 애플리케이션을 정의합니다.
- 텔레그램 메시지 수집 및 분석
- RAG 기반 질의응답
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1 import api_router
from app.core.config import settings

# FastAPI 앱 생성
app = FastAPI(
    title="탤래그램 API",
    description="주식 관련 데이터 분석 및 RAG 서비스",
    version="1.0.0"
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 실제 운영 환경에서는 구체적인 origin으로 변경
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API 라우터 등록
app.include_router(api_router)

# 헬스체크 엔드포인트
@app.get("/health")
async def health_check():
    """서버 상태 확인"""
    return {"status": "healthy"}
