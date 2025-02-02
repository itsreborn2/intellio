from fastapi import FastAPI

# FastAPI 애플리케이션 인스턴스 생성
app = FastAPI(title="Common API Service")

# 헬스 체크 엔드포인트
@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "ok"}
