// AIChatArea의 채팅 관련 타입 정의
import { IChatSession } from '@/types/api/chat';
import { StockOption } from './stock';


/**
 * 채팅 메시지 타입 정의
 */
export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'status';
  content: string;
  content_expert?: string;
  timestamp: number;
  stockInfo?: {
    stockName: string;
    stockCode: string;
  };
  components?: MessageComponent[]; // 구조화된 메시지 컴포넌트 배열 추가
  responseId?: string; // 분석 결과의 고유 ID
  isProcessing?: boolean; // 처리 중 상태
  agent?: string; // 에이전트 정보
  elapsed?: number; // 경과 시간 (초 단위)
  elapsedStartTime?: number; // 경과 시간 시작 타임스탬프
  _forceUpdate?: number; // UI 리렌더링을 강제하기 위한 임의의 값
  metadata?: { // 메타데이터 추가
    components?: MessageComponent[]; // 구조화된 컴포넌트
    responseId?: string; // 응답 ID
    isProcessing?: boolean; // 처리 중 상태
    agent?: string; // 에이전트 정보
    elapsed?: number; // 경과 시간
    stockInfo?: { // 종목 정보
      stockName: string;
      stockCode: string;
    };
    content?: string; // 구조화된 응답 전체 내용
  };
}

/**
 * 메시지 처리를 위한 콜백 함수 타입들
 */
export interface MessageCallbacks {
  onStart?: () => void;
  onAgentStart?: (data: { agent: string; message: string; elapsed: number }) => void;
  onAgentComplete?: (data: { agent: string; message: string; elapsed: number }) => void;
  onComplete?: (data: { 
    message_id: string; 
    response: string; 
    response_expert?: string; 
    metadata?: any 
  }) => void;
  onError?: (error: Error) => void;
}

/**
 * 채팅 컨텍스트 상태 정의
 */
export interface ChatContextState {
  messages: ChatMessage[];
  isProcessing: boolean;
  selectedStock: StockOption | null;
  isInputCentered: boolean;
  showTitle: boolean;
  responseMessage: string;
  statusMessage: string;
  currentChatSession: IChatSession | null;
  copyStates: Record<string, boolean>;
  expertMode: Record<string, boolean>;
  elapsedTime: number;
}


// 모든 메시지 컴포넌트의 기본 인터페이스
export interface IMessageComponentBase {
  type: string;
}

// --- 복합 컴포넌트 인터페이스 ---
export interface IBarChartData {
  labels: string[];
  datasets: Array<{ label: string; data: number[]; [key: string]: any }>;
}

export interface IBarChartComponent extends IMessageComponentBase {
  type: 'bar_chart';
  title?: string;
  data: IBarChartData;
}

export interface ILineChartData {
    labels: string[];
    datasets: Array<{ label: string; data: number[]; [key: string]: any }>;
}

export interface ILineChartComponent extends IMessageComponentBase {
    type: 'line_chart';
    title?: string;
    data: ILineChartData;
}

export interface IMixedChartData {
    labels: string[];
    bar_datasets: Array<{ label: string; data: number[]; [key: string]: any }>;
    line_datasets: Array<{ label: string; data: number[]; [key: string]: any }>;
    y_axis_left_title?: string;
    y_axis_right_title?: string;
}

export interface IMixedChartComponent extends IMessageComponentBase {
    type: 'mixed_chart';
    title?: string;
    data: IMixedChartData;
}

export interface IPriceChartData {
    symbol: string;
    name: string;
    candle_data: Array<{ time: string; open: number; high: number; low: number; close: number; volume: number; price_change_percent: number; [key: string]: any }>;
    volume_data?: Array<{ time: string; value: number; color?: string; [key: string]: any }>;
    moving_averages?: Array<{ time: string; value: number; label: string; color?: string; [key: string]: any }>;
    support_lines?: Array<{ price: number; label?: string; color?: string; [key: string]: any }>;
    resistance_lines?: Array<{ price: number; label?: string; color?: string; [key: string]: any }>;
    period?: string;
    interval?: string;
    metadata?: Record<string, any>;
}

export interface IPriceChartComponent extends IMessageComponentBase {
    type: 'price_chart';
    title?: string;
    data: IPriceChartData;
}

export interface ITechnicalIndicatorData {
    name: string;
    data: number[];
    color?: string;
    chart_type: 'line' | 'bar' | 'area';
    y_axis_id?: string;
    line_style: 'solid' | 'dashed' | 'dotted';
}

export interface ITechnicalIndicatorChartData {
    symbol: string;
    name: string;
    dates: string[];
    candle_data?: Array<{ time: string; open: number; high: number; low: number; close: number; volume: number; price_change_percent: number;[key: string]: any }>;
    indicators: ITechnicalIndicatorData[];
    y_axis_configs?: Record<string, Record<string, any>>;
    period?: string;
    metadata?: Record<string, any>;
}

export interface ITechnicalIndicatorChartComponent extends IMessageComponentBase {
    type: 'technical_indicator_chart';
    title?: string;
    data: ITechnicalIndicatorChartData;
}

export interface IImageComponent extends IMessageComponentBase {
  type: 'image';
  url: string;
  alt?: string;
  caption?: string;
}

export interface ITableHeader {
    key: string;
    label: string;
}

export interface ITableData {
    headers: ITableHeader[];
    rows: Array<Record<string, any>>;
}

export interface ITableComponent extends IMessageComponentBase {
    type: 'table';
    title?: string;
    data: ITableData;
}

// --- 세분화된 텍스트 컴포넌트 인터페이스 ---
export interface IHeadingComponent extends IMessageComponentBase {
  type: 'heading';
  level: 1 | 2 | 3 | 4 | 5 | 6;
  content: string;
}

export interface IParagraphComponent extends IMessageComponentBase {
  type: 'paragraph';
  content: string;
}

export interface IListItem {
  content: string;
}

export interface IListComponent extends IMessageComponentBase {
  type: 'list';
  ordered: boolean;
  items: IListItem[];
}

export interface ICodeBlockComponent extends IMessageComponentBase {
  type: 'code_block';
  language?: string;
  content: string;
}

// --- 메시지 컴포넌트 Union 타입 ---
export type MessageComponent =
  | IHeadingComponent
  | IParagraphComponent
  | IListComponent
  | ICodeBlockComponent
  | IBarChartComponent
  | ILineChartComponent
  | IImageComponent
  | ITableComponent
  | IMixedChartComponent
  | IPriceChartComponent
  | ITechnicalIndicatorChartComponent;

// --- 'complete' SSE 이벤트 데이터 인터페이스 ---
export interface IStructuredChatResponseData {
  message_id: string;
  content: string;
  components: MessageComponent[];
  metadata?: Record<string, any>;
  timestamp: number;
  elapsed: number;
}

/**
 * 채팅 컨텍스트 액션 정의
 */
export type ChatAction =
  | { type: 'ADD_MESSAGE'; payload: ChatMessage }
  | { type: 'UPDATE_MESSAGE'; payload: { id: string; message: Partial<ChatMessage> | Record<string, any> } }
  | { type: 'REMOVE_MESSAGE'; payload: string }
  | { type: 'SET_SELECTED_STOCK'; payload: StockOption | null }
  | { type: 'SET_PROCESSING'; payload: boolean }
  | { type: 'SET_INPUT_CENTERED'; payload: boolean }
  | { type: 'SET_SHOW_TITLE'; payload: boolean }
  | { type: 'SET_CHAT_SESSION'; payload: IChatSession | null }
  | { type: 'RESET_CHAT' }
  | { type: 'TOGGLE_EXPERT_MODE'; payload: string }
  | { type: 'SET_COPY_STATE'; payload: { id: string; state: boolean } }
  | { type: 'SET_ELAPSED_TIME'; payload: number }
  | { type: 'SET_ALL_MESSAGES'; payload: ChatMessage[] }; 