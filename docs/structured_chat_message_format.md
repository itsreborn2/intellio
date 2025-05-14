# 구조화된 채팅 메시지 형식 정의 및 구현 방안

## 1. 문제 정의

현재 StockEasy 채팅 시스템의 백엔드-프론트엔드 간 메시지 전달은 단순 텍스트(`response`, `content_expert`)에 의존하고 있습니다. 이 방식은 다음과 같은 한계점을 가집니다.

*   **표현력 부족:** 텍스트 외에 차트(막대, 선), 이미지, 테이블 등 다양한 형식의 정보를 효과적으로 전달하고 표시하기 어렵습니다.
*   **구조적 정보 손실:** AI가 생성한 답변 내의 계층 구조(제목, 목록 등)나 특정 데이터(표 데이터, 차트 수치)의 의미론적 구조가 텍스트로 변환되면서 손실됩니다.
*   **확장성 제한:** 새로운 정보 유형(예: 비디오, 오디오, 사용자 정의 인터랙티브 컴포넌트)을 추가하기 어렵습니다.

## 2. 제안된 솔루션: 구조화된 컴포넌트 기반 메시지

이러한 한계를 극복하기 위해, AI 어시스턴트의 답변 메시지를 **의미론적 단위의 컴포넌트(Component) 객체들의 배열(List)**로 구조화하는 방식을 제안합니다.

*   각 컴포넌트는 `type` 필드를 통해 자신의 유형(제목, 단락, 막대 차트, 이미지 등)을 명시합니다.
*   `payload` (또는 각 타입별 필드)는 해당 유형에 맞는 데이터를 담습니다.
*   하나의 완전한 AI 답변은 이러한 컴포넌트 객체들의 **순서 있는 리스트**로 구성됩니다.
*   이 리스트 전체가 **단일 JSON 객체**로서 데이터베이스의 한 행에 저장되고, SSE를 통해 프론트엔드로 전달됩니다.
*   프론트엔드는 수신된 컴포넌트 리스트를 순회하며 각 컴포넌트 타입에 맞는 UI를 렌더링합니다.

## 3. 핵심 원칙

*   **메시지 무결성:** 하나의 답변을 구성하는 모든 요소와 순서는 단일 JSON 객체 내에 보존됩니다.
*   **확장성:** 새로운 컴포넌트 타입을 정의하고 추가하기 용이합니다.
*   **명확성:** 각 컴포넌트의 역할과 데이터 구조가 명확합니다.
*   **관심사 분리:** 백엔드는 구조화된 데이터 생성, 프론트엔드는 해당 구조 렌더링에 집중합니다.

## 4. 데이터 구조 정의

### 4.1. 백엔드 (Pydantic 모델 - 예: `common/schemas/chat_components.py`)

```python
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Literal, Union, Optional

# --- 복합 컴포넌트 ---
class BarChartData(BaseModel):
    labels: List[str]
    datasets: List[Dict[str, Any]] # e.g., [{'label': '매출', 'data': [100, 120]}, ...]

class BarChartComponent(BaseModel):
    type: Literal['bar_chart'] = 'bar_chart'
    title: Optional[str] = None
    data: BarChartData

class LineChartData(BaseModel):
    labels: List[str]
    datasets: List[Dict[str, Any]] # e.g., [{'label': '주가', 'data': [50000, 52000]}]

class LineChartComponent(BaseModel):
    type: Literal['line_chart'] = 'line_chart'
    title: Optional[str] = None
    data: LineChartData

class ImageComponent(BaseModel):
    type: Literal['image'] = 'image'
    url: str
    alt: Optional[str] = None
    caption: Optional[str] = None # 이미지 설명

class TableHeader(BaseModel):
    key: str # 데이터 매핑용 키
    label: str # 표시될 헤더 이름

class TableData(BaseModel):
    headers: List[TableHeader]
    rows: List[Dict[str, Any]] # 각 row는 {header.key: value} 형태의 딕셔너리

class TableComponent(BaseModel):
    type: Literal['table'] = 'table'
    title: Optional[str] = None
    data: TableData

# --- 세분화된 텍스트 컴포넌트 ---
class HeadingComponent(BaseModel):
    type: Literal['heading'] = 'heading'
    level: int = Field(..., ge=1, le=6, description="제목 레벨 (1-6)")
    content: str = Field(..., description="제목 텍스트")

class ParagraphComponent(BaseModel):
    type: Literal['paragraph'] = 'paragraph'
    content: str = Field(..., description="단락 텍스트 (인라인 서식은 Markdown 미지원)")

class ListItemComponent(BaseModel):
    content: str
    # sub_items: Optional[List['ListItemComponent']] = None # 추후 중첩 리스트 지원 시

class ListComponent(BaseModel):
    type: Literal['list'] = 'list'
    ordered: bool = Field(default=False, description="순서 있는 목록 여부 (True: <ol>, False: <ul>)")
    items: List[ListItemComponent] = Field(..., description="목록 항목들")

class CodeBlockComponent(BaseModel):
    type: Literal['code_block'] = 'code_block'
    language: Optional[str] = Field(None, description="코드 언어 (syntax highlighting용)")
    content: str = Field(..., description="코드 내용")

# --- 모든 컴포넌트 타입의 Union ---
MessageComponent = Union[
    HeadingComponent,
    ParagraphComponent,
    ListComponent,
    CodeBlockComponent,
    BarChartComponent,
    LineChartComponent,
    ImageComponent,
    TableComponent,
    # 필요시 추가 컴포넌트 정의
]

# --- SSE 'complete' 이벤트로 전송될 최종 구조 ---
class StructuredChatResponse(BaseModel):
    message_id: str # 해당 메시지의 DB ID
    components: List[MessageComponent] # AI 답변을 구성하는 컴포넌트 리스트
    metadata: Optional[Dict[str, Any]] = None # 기존 메타데이터 유지 (처리 시간 등)
    timestamp: float
    elapsed: float

```

### 4.2. 프론트엔드 (TypeScript 인터페이스 - 예: `frontend/types/index.ts`)

```typescript
// 모든 메시지 컴포넌트의 기본 인터페이스
interface IMessageComponentBase {
  type: string;
}

// --- 복합 컴포넌트 인터페이스 ---
interface IBarChartData {
  labels: string[];
  datasets: Array<{ label: string; data: number[]; [key: string]: any }>;
}

interface IBarChartComponent extends IMessageComponentBase {
  type: 'bar_chart';
  title?: string;
  data: IBarChartData;
}

interface ILineChartData {
    labels: string[];
    datasets: Array<{ label: string; data: number[]; [key: string]: any }>;
}

interface ILineChartComponent extends IMessageComponentBase {
    type: 'line_chart';
    title?: string;
    data: ILineChartData;
}

interface IImageComponent extends IMessageComponentBase {
  type: 'image';
  url: string;
  alt?: string;
  caption?: string;
}

interface ITableHeader {
    key: string;
    label: string;
}

interface ITableData {
    headers: ITableHeader[];
    rows: Array<Record<string, any>>;
}

interface ITableComponent extends IMessageComponentBase {
    type: 'table';
    title?: string;
    data: ITableData;
}

// --- 세분화된 텍스트 컴포넌트 인터페이스 ---
interface IHeadingComponent extends IMessageComponentBase {
  type: 'heading';
  level: 1 | 2 | 3 | 4 | 5 | 6;
  content: string;
}

interface IParagraphComponent extends IMessageComponentBase {
  type: 'paragraph';
  content: string;
}

interface IListItem {
  content: string;
  // subItems?: IListItem[]; // 추후 중첩 리스트 지원 시
}

interface IListComponent extends IMessageComponentBase {
  type: 'list';
  ordered: boolean;
  items: IListItem[];
}

interface ICodeBlockComponent extends IMessageComponentBase {
  type: 'code_block';
  language?: string;
  content: string;
}

// --- 메시지 컴포넌트 Union 타입 ---
type MessageComponent =
  | IHeadingComponent
  | IParagraphComponent
  | IListComponent
  | ICodeBlockComponent
  | IBarChartComponent
  | ILineChartComponent
  | IImageComponent
  | ITableComponent
  // 필요시 추가 컴포넌트 타입
  ;

// --- 메인 ChatMessage 인터페이스 업데이트 ---
interface IChatMessage {
  id: string; // DB 상의 UUID 또는 고유 식별자
  role: 'user' | 'assistant' | 'status'; // 메시지 역할
  components?: MessageComponent[]; // 어시스턴트 메시지 내용 (구조화됨)
  content?: string; // 사용자 메시지 내용 또는 단순 텍스트 응답용 (하위호환성)
  timestamp: number; // Unix timestamp (밀리초)
  stockInfo?: { stockName: string; stockCode: string }; // 관련 종목 정보
  // 'status' 메시지 관련 필드 (예: 처리중 상태 표시용)
  isProcessing?: boolean;
  agent?: string;
  elapsed?: number;
  // 기타 메타데이터
  metadata?: Record<string, any>;
}

// --- 'complete' SSE 이벤트 데이터 인터페이스 ---
interface IStructuredChatResponseData {
  message_id: string;
  components: MessageComponent[];
  metadata?: Record<string, any>;
  timestamp: number; // Unix timestamp (초)
  elapsed: number;
}
```

## 5. 백엔드 변경 사항

### 5.1. DB 스키마 변경

*   `ChatMessage` (또는 해당 테이블) 모델/테이블에 `components` 컬럼을 추가합니다.
*   데이터 타입은 `JSON` 또는 `JSONB` (PostgreSQL 권장)로 설정합니다.
*   기존 `content`, `content_expert` 컬럼은 `user` 메시지용으로 남기거나, `assistant` 메시지의 경우 `NULL` 처리 또는 제거를 고려합니다. (일관성을 위해 `assistant`도 `components`만 사용 권장)

### 5.2. `ChatService` 수정

*   `create_chat_message` 및 `update_chat_message` (또는 관련 메서드)를 수정합니다.
*   `assistant` 역할의 메시지를 저장할 때, 입력받은 `List[MessageComponent]` (Pydantic 모델 리스트)를 `List[Dict]` 형태로 변환하여(`[comp.dict() for comp in components]`) 새로 추가된 `components` 컬럼에 저장하도록 합니다.
*   기존 `content`, `content_expert` 컬럼 처리 방침에 따라 해당 컬럼 값 저장을 조정합니다.

### 5.3. RAG 서비스 (`StockRAGService`) 수정

*   AI 모델(LLM) 호출 및 결과 처리 로직을 수정합니다.
*   최종 결과를 단순 텍스트(`answer`, `summary`)가 아닌, 위에서 정의한 **`List[MessageComponent]` (Pydantic 모델 리스트)** 형태로 생성하여 반환하도록 변경합니다.
    *   예: 분석 결과를 바탕으로 `HeadingComponent`, `ParagraphComponent`, `BarChartComponent` 등을 조합하여 리스트를 구성합니다.

### 5.4. SSE 이벤트 스트리밍 (`chat.py`의 `stream_chat_message`) 수정

*   `event_generator` 함수 내에서 `StockRAGService`로부터 `List[MessageComponent]` 결과를 받습니다.
*   `complete` 이벤트 전송 시, `StructuredChatResponse` Pydantic 모델을 사용하여 페이로드를 구성합니다.
    *   `message_id`: DB에 저장된 어시스턴트 메시지의 ID
    *   `components`: RAG 서비스로부터 받은 `List[MessageComponent]`
    *   `metadata`, `timestamp`, `elapsed`: 기존 정보 유지
*   구성된 `StructuredChatResponse` 객체를 `.dict()` 메서드로 Python 딕셔너리로 변환 후 `json.dumps()`를 사용하여 SSE 데이터로 전송합니다. 기존 `response`, `content_expert` 필드는 제거합니다.
*   DB 저장 로직 (`ChatService` 호출 부분)도 `components` 컬럼에 저장하도록 수정합니다.

## 6. 프론트엔드 변경 사항

### 6.1. 타입 정의 (`frontend/types/index.ts`)

*   위 4.2.에서 정의한 TypeScript 인터페이스(`IMessageComponentBase`, 각 컴포넌트 타입, `MessageComponent` 유니온, 업데이트된 `IChatMessage`, `IStructuredChatResponseData`)를 추가/수정합니다.

### 6.2. SSE 이벤트 처리 로직 수정 (`useMessageProcessing` 등)

*   SSE `complete` 이벤트 수신 시, `event.data`를 `JSON.parse()`하여 `IStructuredChatResponseData` 타입으로 캐스팅합니다.
*   메시지 상태 업데이트 함수 (`updateMessage` 또는 관련 Zustand 액션) 호출 시, 파싱된 데이터에서 `components: eventData.components`를 사용하여 메시지 객체의 `components` 필드를 업데이트합니다. (`content` 필드는 `undefined` 또는 기존 값 유지 정책에 따름)

### 6.3. `MessageList.tsx` (또는 메시지 렌더링 컴포넌트) 수정

*   메시지 배열을 순회하며 렌더링하는 로직을 수정합니다.
*   `message.role === 'assistant'`일 경우, `message.components` 배열이 있는지 확인합니다.
*   배열이 존재하면, 이를 순회하며 각 `component` 객체를 새로 만들 `MessageComponentRenderer` 컴포넌트로 전달하여 렌더링합니다.
*   기존 `content` 필드를 사용하는 로직은 `user` 메시지 또는 하위 호환성을 위해 유지/조정합니다.

### 6.4. `MessageComponentRenderer.tsx` 신규 생성

*   `component: MessageComponent` 객체를 props로 받습니다.
*   `switch (component.type)` 문을 사용하여 각 컴포넌트 타입별로 적절한 렌더링 로직을 구현합니다.
    *   `heading`: `h1` ~ `h6` 태그 렌더링 ( `component.level` 사용)
    *   `paragraph`: `p` 태그 렌더링
    *   `list`: `ul` 또는 `ol` 태그와 내부 `li` 태그 렌더링 ( `component.ordered`, `component.items` 사용)
    *   `code_block`: `pre` 와 `code` 태그 렌더링 (Syntax Highlighting 라이브러리 연동 고려 - 예: `react-syntax-highlighter`)
    *   `bar_chart`, `line_chart`: 차트 라이브러리 (예: `Recharts`, `Chart.js`) 컴포넌트 사용하여 렌더링
    *   `image`: `next/image` 또는 `img` 태그 사용하여 렌더링
    *   `table`: `table`, `thead`, `tbody`, `tr`, `th`, `td` 태그 또는 UI 라이브러리(예: `shadcn/ui Table`) 사용하여 렌더링
    *   알 수 없는 타입에 대한 fallback 처리 (예: 경고 로그, JSON 출력)

## 7. 기대 효과

*   **풍부한 정보 표현:** 텍스트 외 다양한 시각적 요소(차트, 이미지, 테이블 등)를 채팅 인터페이스 내에서 직접 제공하여 사용자 경험 향상.
*   **향상된 가독성:** 제목, 목록 등 구조화된 텍스트 렌더링으로 정보 파악 용이성 증대.
*   **미래 확장성 확보:** 새로운 데이터 유형이나 커스텀 컴포넌트를 쉽게 추가할 수 있는 기반 마련.
*   **코드 유지보수성 향상:** 백엔드와 프론트엔드 간의 명확한 데이터 계약으로 개발 및 디버깅 용이성 증대. 