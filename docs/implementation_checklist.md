# 구조화된 채팅 메시지 형식 구현 체크리스트

## Ⅰ. 백엔드 변경 사항 (Python/FastAPI/SQLAlchemy)

1.  **[x] DB 스키마 마이그레이션:**
    *   [x] `ChatMessage` SQLAlchemy 모델(`common/models/chat.py` 또는 관련 파일)에 `components` 컬럼 추가 ( `sqlalchemy.dialects.postgresql.JSONB` 또는 `sqlalchemy.JSON` 타입 사용).
    *   [x] Alembic 또는 사용하는 마이그레이션 도구를 사용하여 DB 스키마 변경 적용 (`alembic revision --autogenerate`, `alembic upgrade head`).
    *   [x] 기존 `content`, `content_expert` 컬럼 처리 방안 결정 및 반영 (예: `assistant` 메시지의 경우 nullable 하게 변경).

2.  **[x] 공통 스키마 정의:**
    *   [x] `common/schemas/chat_components.py` 파일 생성 또는 기존 파일에 Pydantic 모델 정의 ( `HeadingComponent`, `ParagraphComponent`, `ListComponent`, `CodeBlockComponent`, `BarChartComponent`, `LineChartComponent`, `ImageComponent`, `TableComponent`, `MessageComponent` Union, `StructuredChatResponse`).

3.  **[x] `ChatService` 수정 (`stockeasy/services/chat_service.py`):**
    *   [x] `create_chat_message` / `update_chat_message` 메서드 수정:
        *   `assistant` 역할 메시지 저장 시 `components: List[MessageComponent]` 인자를 받도록 변경.
        *   입력받은 컴포넌트 리스트를 `[comp.dict() for comp in components]` 로 변환하여 DB의 `components` 컬럼에 저장.
        *   결정된 정책에 따라 `content`, `content_expert` 컬럼 값 처리.

4.  **[x] RAG 서비스 수정 (`stockeasy/services/rag_service.py` 및 관련 모듈):**
    *   [x] LLM 호출 및 결과 처리 로직 수정: 최종 분석 결과를 단순 텍스트가 아닌 **`List[MessageComponent]` (Pydantic 모델 리스트)** 형태로 구성하여 반환하도록 변경. (가장 복잡한 부분일 수 있음, LLM 프롬프트 및 후처리 로직 수정 필요)
        *   [x] 텍스트 요소는 `HeadingComponent`, `ParagraphComponent`, `ListComponent`, `CodeBlockComponent` 등으로 변환.
        *   [x] 차트, 테이블 데이터는 `BarChartComponent`, `LineChartComponent`, `TableComponent` 등으로 변환.
        *   [x] 이미지 관련 정보는 `ImageComponent`로 변환.

5.  **[x] SSE 스트리밍 로직 수정 (`stockeasy/api/v1/chat.py`의 `stream_chat_message`):**
    *   [x] `event_generator` 내에서 RAG 서비스로부터 `List[MessageComponent]` 받기.
    *   [x] DB에 어시스턴트 메시지 저장 시 (`ChatService` 호출), `components` 데이터를 전달하도록 수정. 저장 후 반환되는 `message_id` 확인.
    *   [x] `complete` SSE 이벤트 전송 시:
        *   `StructuredChatResponse` Pydantic 모델 사용하여 페이로드 구성 (`message_id`, `components`, `metadata`, `timestamp`, `elapsed`).
        *   `.dict()` 호출 및 `json.dumps()` 로 JSON 문자열 변환하여 전송.
        *   기존 `response`, `content_expert` 관련 로직 제거.

## Ⅱ. 프론트엔드 변경 사항 (TypeScript/Next.js/React)

6.  **[x] 타입 정의 (`frontend/types/index.ts`):**
    *   [x] `IMessageComponentBase`, 각 컴포넌트 타입 인터페이스(`IHeadingComponent` 등), `MessageComponent` 유니온 타입, 업데이트된 `IChatMessage`, `IStructuredChatResponseData` 인터페이스 추가/수정.

7.  **[x] SSE 이벤트 처리 로직 수정 (`frontend/stockeasy/app/components/chat/AIChatArea/hooks/useMessageProcessing.ts` 또는 관련 파일):**
    *   [x] `complete` 이벤트 핸들러에서 `event.data`를 `IStructuredChatResponseData` 타입으로 파싱.
    *   [x] 메시지 상태 업데이트 로직 (`updateMessage` 또는 Zustand 액션)에서 `components: eventData.components`를 `IChatMessage` 객체에 저장하도록 수정.

8.  **[x] 메시지 렌더링 컴포넌트 수정 (`frontend/stockeasy/app/components/chat/AIChatArea/components/MessageList.tsx`):**
    *   [x] `assistant` 역할 메시지 렌더링 시 `message.components` 배열을 순회하도록 변경.
    *   [x] 각 `component` 객체를 `MessageComponentRenderer` 컴포넌트에 props로 전달.

9.  **[x] `MessageComponentRenderer.tsx` 신규 생성 (`frontend/stockeasy/app/components/chat/AIChatArea/components/MessageComponentRenderer.tsx`):**
    *   [x] `component: MessageComponent` props 정의.
    *   [x] `switch (component.type)` 문 구현.
    *   [x] 각 `case`별 기본 HTML 태그 또는 플레이스홀더 렌더링 구현 (아래 10단계에서 구체화).

10. **[x] 각 컴포넌트 타입별 UI 구현 (`MessageComponentRenderer.tsx` 및 하위 컴포넌트):**
    *   [x] `heading`: `<h1>` ~ `<h6>` 렌더링.
    *   [x] `paragraph`: `<p>` 렌더링.
    *   [x] `list`: `<ul>`, `<ol>`, `<li>` 렌더링.
    *   [x] `code_block`: `<pre><code>` 렌더링 ( `react-syntax-highlighter` 등 라이브러리 연동).
    *   [x] `bar_chart`, `line_chart`: 차트 라이브러리 (`Recharts`, `Chart.js` 등) 연동 및 렌더링.
    *   [x] `image`: `next/image` 또는 `<img>` 렌더링.
    *   [x] `table`: `shadcn/ui Table` 또는 직접 `<table>` 구조 렌더링.

## Ⅲ. 테스트 및 검증

11. **[ ] 단위/통합 테스트:**
    *   [ ] 백엔드: 컴포넌트 생성 로직, DB 저장/조회, SSE 전송 데이터 형식 검증.
    *   [ ] 프론트엔드: SSE 수신 데이터 파싱, 각 컴포넌트 렌더링 결과 검증.
12. **[ ] E2E 테스트:** 실제 시나리오(다양한 질문 유형)를 통해 전체 흐름 및 UI/UX 검증. 