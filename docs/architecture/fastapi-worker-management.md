# FastAPI 워커 관리와 고부하 요청 처리 전략

## 문제 상황

FastAPI가 여러 워커로 구동되는 환경에서 발생하는 문제:

1. 채팅 요청(`stream_chat_message`)과 같은 처리 시간이 긴 요청(약 2분)이 있음
2. 여러 사용자가 동시에 질문을 하면 모든 FastAPI 워커가 이러한 요청을 처리하느라 바쁨
3. 이 상태에서 새로운 요청(예: 주식 정보 조회)이 들어오면 응답이 지연됨

## 해결 방안

### 1. Celery 작업으로 처리하기

현재 이미 Celery가 설정되어 있으므로, 처리 시간이 긴 작업을 Celery로 분리:

```python
@chat_router.post("/sessions/{chat_session_id}/messages/stream")
async def stream_chat_message(
    chat_session_id: UUID = Path(...),
    request: ChatMessageStreamRequest = Body(...),
    db: AsyncSession = Depends(get_db_async),
    current_session: Session = Depends(get_current_session)
) -> EventSourceResponse:
    # 사용자 메시지 저장
    user_message = await ChatService.create_chat_message(
        db=db,
        chat_session_id=chat_session_id,
        role="user",
        content=request.message,
        stock_code=request.stock_code,
        stock_name=request.stock_name
    )
    
    # Celery 작업으로 실행
    task = process_chat_message.delay(
        str(chat_session_id),
        request.message,
        request.stock_code,
        request.stock_name,
        str(current_session.id),
        str(current_session.user_id)
    )
    
    # SSE 설정하여 클라이언트에게 작업 진행 상태 스트리밍
    async def event_generator():
        yield json.dumps({
            "event": "start",
            "data": {
                "task_id": task.id,
                "message": "질문 처리를 시작합니다.",
                "timestamp": time.time()
            }
        })
        
        # Celery 작업 상태 폴링 및 결과 스트리밍
        # ...
        
    return EventSourceResponse(event_generator())
```

### 2. Nginx를 통한 로드 밸런싱 전략

FastAPI 앞단에 Nginx를 로드 밸런서로 구성하여 특정 엔드포인트를 지정된 워커로만 라우팅:

```nginx
# 일반 API 처리용 백엔드 그룹
upstream fastapi_general {
    server fastapi:8000 weight=3;
    server fastapi:8001 weight=3;
}

# 무거운 작업 처리용 백엔드 그룹
upstream fastapi_heavy {
    server fastapi:8002;
}

server {
    # ...
    
    # 일반 API 요청 라우팅
    location /api/v1/ {
        proxy_pass http://fastapi_general;
        # ...
    }
    
    # 채팅 스트리밍 요청만 특정 워커로 라우팅
    location /api/v1/stockeasy/chat/sessions/*/messages/stream {
        proxy_pass http://fastapi_heavy;
        # SSE 설정
        proxy_http_version 1.1;
        proxy_set_header Connection '';
        proxy_buffering off;
        # ...
    }
}
```

### 3. Redis 기반 Queue 시스템 구현

이미 Redis가 설정된 환경에서 자체 큐 시스템 구현:

```python
@chat_router.post("/sessions/{chat_session_id}/messages/stream")
async def stream_chat_message(
    chat_session_id: UUID = Path(...),
    request: ChatMessageStreamRequest = Body(...),
    db: AsyncSession = Depends(get_db_async),
    current_session: Session = Depends(get_current_session)
) -> JSONResponse:
    # 사용자 메시지 저장
    user_message = await ChatService.create_chat_message(...)
    
    # 요청 ID 생성
    request_id = str(uuid4())
    
    # Redis에 요청 저장
    await async_redis_client.set_key(
        f"chat_request:{request_id}",
        {
            "chat_session_id": str(chat_session_id),
            "message": request.message,
            "stock_code": request.stock_code,
            "stock_name": request.stock_name,
            "session_id": str(current_session.id),
            "user_id": str(current_session.user_id),
            "status": "pending",
            "created_at": time.time()
        }
    )
    
    # 요청을 큐에 추가
    await async_redis_client.rpush("chat_request_queue", request_id)
    
    # 클라이언트에게 요청 ID와 상태 확인 URL 반환
    return JSONResponse({
        "request_id": request_id,
        "status": "pending",
        "status_url": f"/api/v1/stockeasy/chat/requests/{request_id}/status",
        "result_url": f"/api/v1/stockeasy/chat/requests/{request_id}/result"
    })
```

별도의 워커 프로세스가 큐에서 요청을 처리하도록 구현

### 4. 사용자/요청별 Rate Limiting 구현

Redis를 사용하여 사용자별 요청 제한 구현:

```python
@chat_router.post("/sessions/{chat_session_id}/messages/stream")
async def stream_chat_message(
    # ... 기존 매개변수
):
    # 사용자당 처리 중인 요청 수 확인
    processing_count = await async_redis_client.get_key(f"user:{current_session.user_id}:processing_count") or 0
    
    if int(processing_count) >= 1:
        # 이미 처리 중인 요청이 있음
        return JSONResponse(
            status_code=429,  # Too Many Requests
            content={"detail": "이미 처리 중인 요청이 있습니다. 완료 후 다시 시도해주세요."}
        )
    
    # 처리 중인 요청 카운터 증가
    await async_redis_client.incr(f"user:{current_session.user_id}:processing_count")
    
    try:
        # 기존 로직 실행
        # ...
    finally:
        # 처리 완료 후 카운터 감소
        await async_redis_client.decr(f"user:{current_session.user_id}:processing_count")
```

## 싱글턴 클래스와 Redis를 활용한 데이터 공유

FastAPI 워커가 여러 개 실행되면, 각 워커는 독립적인 프로세스로 실행되어 메모리 공간이 분리됩니다. 이로 인해 싱글턴 클래스(예: StockInfoService)도 각 워커마다 독립적으로 인스턴스화됩니다.

### 문제점
- 각 워커마다 동일한 데이터 중복 저장
- 데이터 일관성 유지 어려움
- 메모리 사용량 증가

### Redis를 사용한 해결 방안

주식 정보와 같이 여러 워커에서 공유해야 하는 데이터는 Redis에 저장하고 공유:

```python
# 주식 데이터 업데이트 전용 워커/태스크
async def update_stock_data_worker():
    while True:
        # KRX에서 데이터 가져오기
        stock_data = await fetch_stock_info_from_krx()
        
        # Redis에 데이터 저장
        for code, info in stock_data.items():
            await async_redis_client.set_key(f"stock:data:{code}", info)
        
        # 전체 리스트 저장
        await async_redis_client.set_key("stock:list", list(stock_data.keys()))
        
        # 하루에 한 번 업데이트 (또는 필요한 간격)
        await asyncio.sleep(86400)

# 다른 워커에서 데이터 접근
async def get_stock_by_code(code: str):
    return await async_redis_client.get_key(f"stock:data:{code}")

async def get_all_stocks():
    codes = await async_redis_client.get_key("stock:list")
    if not codes:
        return []
    
    stocks = []
    for code in codes:
        stock = await get_stock_by_code(code)
        if stock:
            stocks.append(stock)
    
    return stocks
```

### 프론트엔드에서의 데이터 접근

프론트엔드에서 Redis에 직접 접근하는 것은 보안 문제로 권장되지 않습니다. 대신:

1. RESTful API 엔드포인트 제공
2. WebSocket을 통한 실시간 데이터 스트리밍
3. 서버 사이드 렌더링(Next.js 서버 컴포넌트)

## 권장 구현 전략

현재 아키텍처에서 가장 효과적인 방법:

1. **처리 시간이 긴 작업을 Celery로 분리**: 이미 Celery가 설정되어 있으므로 활용
2. **Redis를 통한 데이터 공유**: 주식 정보 등 공통 데이터는 Redis에 저장하여 공유
3. **사용자별 요청 제한**: 사용자당 동시 처리 요청 수 제한하여 시스템 과부하 방지

FastAPI 자체에서는 특정 엔드포인트를 특정 워커로만 라우팅하는 기능이 없으므로, 이를 구현하려면 외부 로드 밸런서(Nginx) 설정이 필요합니다. 