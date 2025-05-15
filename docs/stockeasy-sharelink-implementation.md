# StockEasy 웹링크 공유하기 기능 구현 체크리스트

## 프로젝트 개요
'StockEasy 웹링크 공유하기' 기능은 사용자가 자신의 채팅 내용을 다른 사람과 공유할 수 있도록 링크를 생성하고, 해당 링크로 접속한 사람이 로그인 없이도 채팅 내용을 볼 수 있도록 하는 기능입니다.

## 구현 단계 체크리스트

### 1. 백엔드 구현

#### 1.1 데이터베이스 모델 생성
- [ ] `backend/stockeasy/models/chat.py`에 `ShareStockChatSession` 테이블 추가
  ```python
  class ShareStockChatSession(Base):
      """공유된 주식 채팅 세션 테이블
      
      공유를 위해 복제된 채팅 세션을 나타냅니다.
      """
      __tablename__ = "stockeasy_shared_chat_sessions"
      __table_args__ = (
          {"schema": "stockeasy"}
      )
      
      id: Mapped[PyUUID] = mapped_column(
          UUID, primary_key=True, default=uuid4,
          server_default=text("gen_random_uuid()"),
          comment="공유 세션 ID"
      )
      original_session_id: Mapped[PyUUID] = mapped_column(
          UUID, ForeignKey("stockeasy.stockeasy_chat_sessions.id", ondelete="CASCADE"),
          nullable=False, index=True,
          comment="원본 채팅 세션 ID"
      )
      share_uuid: Mapped[str] = mapped_column(
          String(36), nullable=False, unique=True, index=True,
          comment="공유 링크용 UUID"
      )
      title: Mapped[str] = mapped_column(
          String(255), nullable=False,
          comment="채팅 세션 제목"
      )
      # 종목 정보 필드
      stock_code: Mapped[Optional[str]] = mapped_column(
          String(20), nullable=True, index=True,
          comment="종목 코드"
      )
      stock_name: Mapped[Optional[str]] = mapped_column(
          String(100), nullable=True,
          comment="종목명"
      )
      # 추가 종목 정보를 JSON으로 저장
      stock_info: Mapped[Optional[dict]] = mapped_column(
          JSONB, nullable=True,
          comment="종목 관련 추가 정보"
      )
      # 에이전트 처리 결과 데이터
      agent_results: Mapped[Optional[dict]] = mapped_column(
          JSONB, nullable=True,
          comment="세션의 에이전트 처리 결과 데이터"
      )
      # 역참조 관계
      messages: Mapped[List["ShareStockChatMessage"]] = relationship(
          "ShareStockChatMessage",
          back_populates="session",
          cascade="all, delete-orphan",
          lazy="selectin"
      )
      
      @property
      def to_dict(self) -> dict:
          """세션 객체를 딕셔너리로 변환"""
          return {
              "id": str(self.id),
              "original_session_id": str(self.original_session_id),
              "share_uuid": self.share_uuid,
              "title": self.title,
              "stock_code": self.stock_code,
              "stock_name": self.stock_name,
              "stock_info": self.stock_info,
              "agent_results": self.agent_results,
              "created_at": self.created_at.isoformat() if self.created_at else None,
              "updated_at": self.updated_at.isoformat() if self.updated_at else None
          }
  ```

- [ ] `ShareStockChatMessage` 테이블 추가
  ```python
  class ShareStockChatMessage(Base):
      """공유된 주식 채팅 메시지 테이블
      
      공유된 채팅 세션 내의 개별 메시지를 나타냅니다.
      """
      __tablename__ = "stockeasy_shared_chat_messages"
      __table_args__ = (
          Index("ix_stockeasy_shared_chat_messages_chat_session_id_created_at", 
                "chat_session_id", "created_at"),
          {"schema": "stockeasy"}
      )
      
      id: Mapped[PyUUID] = mapped_column(
          UUID, primary_key=True, default=uuid4,
          server_default=text("gen_random_uuid()"),
          comment="공유 메시지 ID"
      )
      chat_session_id: Mapped[PyUUID] = mapped_column(
          UUID, ForeignKey("stockeasy.stockeasy_shared_chat_sessions.id", ondelete="CASCADE"),
          nullable=False, index=True,
          comment="공유 채팅 세션 ID"
      )
      original_message_id: Mapped[Optional[PyUUID]] = mapped_column(
          UUID, nullable=True,
          comment="원본 메시지 ID"
      )
      role: Mapped[str] = mapped_column(
          String(20), nullable=False,
          comment="메시지 역할 (user, assistant, system)"
      )
      # 기존 StockChatMessage와 동일한 필드들 추가
      stock_code: Mapped[Optional[str]] = mapped_column(
          String(20), nullable=True,
          comment="종목 코드"
      )
      stock_name: Mapped[Optional[str]] = mapped_column(
          String(100), nullable=True,
          comment="종목명"
      )
      content_type: Mapped[str] = mapped_column(
          String(50), nullable=False,
          server_default="text",
          comment="메시지 콘텐츠 타입"
      )
      content: Mapped[Optional[str]] = mapped_column(
          Text, nullable=True,
          comment="메시지 텍스트 내용"
      )
      content_expert: Mapped[Optional[str]] = mapped_column(
          Text, nullable=True,
          comment="전문가 메시지 텍스트 내용"
      )
      components: Mapped[Optional[List[dict]]] = mapped_column(
          JSONB, nullable=True,
          comment="구조화된 메시지 컴포넌트 배열"
      )
      message_data: Mapped[Optional[dict]] = mapped_column(
          JSONB, nullable=True,
          comment="메시지 타입별 구조화된 데이터"
      )
      data_url: Mapped[Optional[str]] = mapped_column(
          Text, nullable=True,
          comment="외부 리소스 URL"
      )
      message_metadata: Mapped[Optional[dict]] = mapped_column(
          JSONB, nullable=True,
          comment="메시지 추가 메타데이터"
      )
      agent_results: Mapped[Optional[dict]] = mapped_column(
          JSONB, nullable=True,
          comment="에이전트 처리 결과 데이터"
      )
      # 세션과의 관계
      session: Mapped["ShareStockChatSession"] = relationship(
          "ShareStockChatSession",
          back_populates="messages",
          foreign_keys=[chat_session_id],
          lazy="joined"
      )
      
      @property
      def to_dict(self) -> dict:
          """메시지 객체를 딕셔너리로 변환"""
          return {
              "id": str(self.id),
              "chat_session_id": str(self.chat_session_id),
              "original_message_id": str(self.original_message_id) if self.original_message_id else None,
              "role": self.role,
              "content_type": self.content_type,
              "content": self.content,
              "content_expert": self.content_expert,
              "components": self.components,
              "stock_code": self.stock_code,
              "stock_name": self.stock_name,
              "message_data": self.message_data,
              "data_url": self.data_url,
              "message_metadata": self.message_metadata,
              "agent_results": self.agent_results,
              "created_at": self.created_at.isoformat() if self.created_at else None,
              "updated_at": self.updated_at.isoformat() if self.updated_at else None
          }
  ```

- [ ] `models/__init__.py` 파일에 새 모델 등록

#### 1.2 스키마(Pydantic 모델) 정의
- [ ] `backend/stockeasy/schemas/chat.py`에 `ShareChatResponse` 추가
  ```python
  # 공유 링크 생성 응답 스키마
  class ShareLinkResponse(BaseModel):
      share_uuid: str
      share_url: str
  
  # 공유된 채팅 세션 응답 스키마
  class SharedChatSessionResponse(BaseModel):
      id: str
      share_uuid: str
      title: str
      stock_code: Optional[str] = None
      stock_name: Optional[str] = None
      stock_info: Optional[dict] = None
      created_at: Optional[datetime] = None
      updated_at: Optional[datetime] = None
  ```

#### 1.3 서비스 로직 구현
- [ ] `backend/stockeasy/services/chat.py`에 공유 링크 생성 서비스 추가
  ```python
  async def create_share_link(
      session_id: UUID,
      db: AsyncSession
  ) -> ShareLinkResponse:
      """채팅 세션 공유 링크 생성
      
      원본 채팅 세션을 복제하여 공유용 세션 생성
      """
      # 채팅 세션 조회
      original_session = await db.get(StockChatSession, session_id)
      if not original_session:
          raise HTTPException(status_code=404, detail="채팅 세션을 찾을 수 없습니다.")
          
      # 공유 UUID 생성
      share_uuid = str(uuid4())
      
      # 공유 세션 생성
      share_session = ShareStockChatSession(
          original_session_id=original_session.id,
          share_uuid=share_uuid,
          title=original_session.title,
          stock_code=original_session.stock_code,
          stock_name=original_session.stock_name,
          stock_info=original_session.stock_info,
          agent_results=original_session.agent_results
      )
      db.add(share_session)
      await db.flush()
      
      # 원본 메시지 복사
      for msg in original_session.messages:
          share_message = ShareStockChatMessage(
              chat_session_id=share_session.id,
              original_message_id=msg.id,
              role=msg.role,
              stock_code=msg.stock_code,
              stock_name=msg.stock_name,
              content_type=msg.content_type,
              content=msg.content,
              content_expert=msg.content_expert,
              components=msg.components,
              message_data=msg.message_data,
              data_url=msg.data_url,
              message_metadata=msg.message_metadata,
              agent_results=msg.agent_results
          )
          db.add(share_message)
      
      await db.commit()
      
      # 공유 URL 생성
      base_url = settings.FRONTEND_URL
      share_url = f"{base_url}/share_chat/{share_uuid}"
      
      return ShareLinkResponse(
          share_uuid=share_uuid,
          share_url=share_url
      )
  ```

- [ ] 공유된 채팅 조회 서비스 추가
  ```python
  async def get_shared_chat_session(
      share_uuid: str,
      db: AsyncSession
  ) -> dict:
      """공유된 채팅 세션 조회
      
      공유 UUID로 세션과 메시지 조회
      """
      # 공유 세션 조회
      query = select(ShareStockChatSession).where(
          ShareStockChatSession.share_uuid == share_uuid
      )
      result = await db.execute(query)
      session = result.scalar_one_or_none()
      
      if not session:
          raise HTTPException(status_code=404, detail="공유된 채팅을 찾을 수 없습니다.")
      
      # 구조화된 응답 생성 (StockChatMessage와 동일한 형식)
      return {
          "session": session.to_dict,
          "messages": [msg.to_dict for msg in session.messages]
      }
  ```

#### 1.4 API 엔드포인트 구현
- [ ] `backend/stockeasy/api/chat.py`에 공유 링크 생성 엔드포인트 추가
  ```python
  @router.get("/share/make_link/{session_id}", response_model=ShareLinkResponse)
  async def create_share_link(
      session_id: UUID,
      db: AsyncSession = Depends(get_db),
      current_user: User = Depends(get_current_user)
  ):
      """채팅 세션 공유 링크 생성 API
      
      인증된 사용자만 자신의 채팅 세션에 대한 공유 링크 생성 가능
      """
      # 세션 소유권 확인
      query = select(StockChatSession).where(
          StockChatSession.id == session_id,
          StockChatSession.user_id == current_user.id
      )
      result = await db.execute(query)
      session = result.scalar_one_or_none()
      
      if not session:
          raise HTTPException(
              status_code=404, 
              detail="채팅 세션을 찾을 수 없거나 접근 권한이 없습니다."
          )
      
      # 공유 링크 생성 서비스 호출
      return await chat_service.create_share_link(session_id, db)
  ```

- [ ] 공유된 채팅 조회 엔드포인트 추가
  ```python
  @router.get("/share/{share_uuid}", response_model=dict)
  async def get_shared_chat(
      share_uuid: str,
      db: AsyncSession = Depends(get_db)
  ):
      """공유된 채팅 세션 조회 API
      
      공유 UUID로 공유된 채팅 세션과 메시지 조회
      인증 없이 접근 가능
      """
      return await chat_service.get_shared_chat_session(share_uuid, db)
  ```

#### 1.5 데이터베이스 마이그레이션
- [ ] Alembic 마이그레이션 스크립트 생성
  ```bash
  alembic revision --autogenerate -m "add share chat tables"
  ```
- [ ] 마이그레이션 실행
  ```bash
  alembic upgrade head
  ```

### 2. 프론트엔드 구현

#### 2.1 공유하기 버튼 추가
- [ ] `frontend/stockeasy/app/components/Header.tsx` 수정
  ```typescript
  // 추가 import
  import { Link, Share } from 'lucide-react';
  import { useToast } from '@/components/ui/use-toast';
  import { useChatShare } from '@/services/api/useChatShare';
  
  // Header 컴포넌트 내부
  // PDF 내보내기 버튼 옆에 공유하기 버튼 추가
  const { toast } = useToast();
  const { isShareLoading, createShareLink } = useChatShare();
  
  // 공유 링크 생성 처리 핸들러
  const handleShareChat = async () => {
    if (!currentSession) {
      toast({
        title: "오류",
        description: "채팅 세션이 없습니다.",
        variant: "destructive"
      });
      return;
    }
    
    try {
      const result = await createShareLink(currentSession.id);
      
      // 클립보드에 링크 복사
      await navigator.clipboard.writeText(result.share_url);
      
      toast({
        title: "공유 링크 생성 완료",
        description: "링크가 클립보드에 복사되었습니다.",
      });
    } catch (error) {
      toast({
        title: "오류",
        description: "공유 링크 생성에 실패했습니다.",
        variant: "destructive"
      });
    }
  };
  
  // JSX 부분 (PDF 버튼 옆에 추가)
  {isUserLoggedIn && hasChatMessages && currentSession && (
    <>
      <button
        onClick={handleShareChat}
        disabled={isShareLoading}
        className="flex items-center gap-1 text-sm px-2.5 py-1 rounded-md bg-[#F5F5F5] hover:bg-[#E5E5E5] transition-colors border border-[#DDD]"
      >
        {isShareLoading ? (
          <Loader2 size={16} className="animate-spin" />
        ) : (
          <Share size={16} />
        )}
        <span className="hidden sm:inline">공유</span>
      </button>
      <button
        onClick={handleSaveAsPdf}
        disabled={isPdfLoading}
        className="flex items-center gap-1 text-sm px-2.5 py-1 rounded-md bg-[#F5F5F5] hover:bg-[#E5E5E5] transition-colors border border-[#DDD]"
      >
        {isPdfLoading ? (
          <Loader2 size={16} className="animate-spin" />
        ) : (
          <Download size={16} />
        )}
        <span className="hidden sm:inline">PDF</span>
      </button>
    </>
  )}
  ```

#### 2.2 API 서비스 구현
- [ ] 공유 링크 API 서비스 추가 (`frontend/stockeasy/services/api/useChatShare.ts`)
  ```typescript
  import { useState } from 'react';
  import { API_BASE_URL } from '@/config';
  
  export interface IShareLinkResponse {
    share_uuid: string;
    share_url: string;
  }
  
  export function useChatShare() {
    const [isShareLoading, setIsShareLoading] = useState<boolean>(false);
    
    // 공유 링크 생성 함수
    const createShareLink = async (sessionId: string): Promise<IShareLinkResponse> => {
      setIsShareLoading(true);
      
      try {
        const response = await fetch(`${API_BASE_URL}/api/v1/stockeasy/chat/share/make_link/${sessionId}`, {
          method: 'GET',
          headers: {
            'Content-Type': 'application/json',
          },
          credentials: 'include',
        });
        
        if (!response.ok) {
          throw new Error('공유 링크 생성 실패');
        }
        
        const data = await response.json();
        return data as IShareLinkResponse;
      } catch (error) {
        console.error('공유 링크 생성 오류:', error);
        throw error;
      } finally {
        setIsShareLoading(false);
      }
    };
    
    // 공유된 채팅 세션 조회 함수
    const getSharedChat = async (shareUuid: string): Promise<any> => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/v1/stockeasy/chat/share/${shareUuid}`, {
          method: 'GET',
          headers: {
            'Content-Type': 'application/json',
          },
        });
        
        if (!response.ok) {
          throw new Error('공유된 채팅 조회 실패');
        }
        
        return await response.json();
      } catch (error) {
        console.error('공유된 채팅 조회 오류:', error);
        throw error;
      }
    };
    
    return {
      isShareLoading,
      createShareLink,
      getSharedChat,
    };
  }
  ```

#### 2.3 공유 페이지 구현
- [ ] 공유 페이지용 라우트 생성 (`frontend/stockeasy/app/share_chat/[shareUuid]/page.tsx`)
  ```typescript
  'use client';
  
  import { useEffect, useState } from 'react';
  import { useParams } from 'next/navigation';
  import { useChatShare } from '@/services/api/useChatShare';
  import ChatMessage from '@/app/components/chat/AIChatArea/components/ChatMessage';
  import { LoadingSpinner } from '@/components/ui/loading-spinner';
  
  export default function SharedChatPage() {
    const params = useParams();
    const shareUuid = params.shareUuid as string;
    const { getSharedChat } = useChatShare();
    
    const [session, setSession] = useState<any>(null);
    const [messages, setMessages] = useState<any[]>([]);
    const [isLoading, setIsLoading] = useState<boolean>(true);
    const [error, setError] = useState<string | null>(null);
    
    useEffect(() => {
      const fetchSharedChat = async () => {
        try {
          setIsLoading(true);
          setError(null);
          
          const data = await getSharedChat(shareUuid);
          setSession(data.session);
          setMessages(data.messages);
        } catch (err) {
          console.error('공유 채팅 로드 실패:', err);
          setError('공유된 채팅을 불러오는데 실패했습니다.');
        } finally {
          setIsLoading(false);
        }
      };
      
      if (shareUuid) {
        fetchSharedChat();
      }
    }, [shareUuid, getSharedChat]);
    
    if (isLoading) {
      return (
        <div className="flex justify-center items-center min-h-screen">
          <LoadingSpinner size="lg" />
        </div>
      );
    }
    
    if (error) {
      return (
        <div className="flex justify-center items-center min-h-screen">
          <div className="p-4 rounded-md bg-red-50 text-red-600">
            {error}
          </div>
        </div>
      );
    }
    
    return (
      <div className="container mx-auto px-4 py-8 max-w-5xl">
        <div className="bg-white rounded-lg shadow-md p-6">
          <h1 className="text-2xl font-bold mb-4 flex items-center">
            {session?.stock_name && (
              <span className="mr-2 px-2 py-1 bg-blue-100 text-blue-800 rounded text-sm">
                {session.stock_name}
              </span>
            )}
            {session?.title || '공유된 채팅'}
          </h1>
          
          <div className="mt-6 border-t border-gray-100 pt-4">
            {messages.length === 0 ? (
              <p className="text-center text-gray-500 py-8">메시지가 없습니다.</p>
            ) : (
              <div className="space-y-6">
                {messages.map((message: any) => (
                  <ChatMessage
                    key={message.id}
                    message={message}
                    isReadOnly={true}
                    userMode="beginner"
                  />
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }
  ```

- [ ] 공유 페이지 레이아웃 생성 (`frontend/stockeasy/app/share_chat/[shareUuid]/layout.tsx`)
  ```typescript
  import { Metadata } from 'next';
  
  export const metadata: Metadata = {
    title: '공유된 채팅 - StockEasy',
    description: 'StockEasy 공유된 주식 채팅 내용',
  };
  
  export default function SharedChatLayout({
    children,
  }: {
    children: React.ReactNode;
  }) {
    return (
      <div className="min-h-screen bg-gray-50">
        <div className="fixed top-0 left-0 w-full h-[44px] bg-[#F4F4F4] z-40 flex items-center px-4">
          <div className="flex justify-between items-center w-full">
            <div className="flex items-center">
              <div className="text-lg font-semibold">StockEasy 공유 채팅</div>
            </div>
          </div>
        </div>
        <div className="pt-[60px]">
          {children}
        </div>
      </div>
    );
  }
  ```

#### 2.4 인증 예외 처리
- [ ] 인증 미들웨어에 공유 페이지 경로 예외 추가 (`frontend/stockeasy/middleware.ts`)
  ```typescript
  // middleware.ts 파일 수정 - 공유 페이지 경로 추가
  export const config = {
    matcher: [
      // 기존 경로들
      '/((?!api|_next/static|_next/image|favicon.ico|images|share_chat).*)',
    ],
  };
  ```

#### 2.5 타입 정의 추가
- [ ] `frontend/types/index.ts`에 공유 관련 타입 추가
  ```typescript
  export interface IShareLinkResponse {
    share_uuid: string;
    share_url: string;
  }
  
  export interface ISharedChatSession {
    id: string;
    share_uuid: string;
    title: string;
    stock_code?: string;
    stock_name?: string;
    stock_info?: any;
    created_at?: string;
    updated_at?: string;
  }
  ```

### 3. 테스트 단계

#### 3.1 백엔드 테스트
- [ ] 데이터베이스 마이그레이션 정상 동작 확인
- [ ] 공유 링크 생성 API 동작 확인
- [ ] 공유된 채팅 조회 API 동작 확인

#### 3.2 프론트엔드 테스트
- [ ] 공유하기 버튼 렌더링 확인
- [ ] 공유 링크 생성 기능 동작 확인
- [ ] 클립보드 복사 및 토스트 알림 확인
- [ ] 생성된 공유 링크로 접속 테스트
- [ ] 로그인 없이 공유 페이지 접근 가능 확인
- [ ] 채팅 메시지 렌더링 확인
- [ ] 다양한 메시지 타입 표시 확인

#### 3.3 크로스 브라우저 테스트
- [ ] Chrome, Firefox, Safari, Edge 등 주요 브라우저 테스트
- [ ] 모바일 환경 테스트 (반응형 디자인 확인)

## 구현 순서 계획

1. 백엔드 마이그레이션 및 모델 구현
   - ShareStockChatSession, ShareStockChatMessage 모델 구현
   - Alembic 마이그레이션 스크립트 생성 및 적용

2. 백엔드 API 구현
   - 공유 링크 생성 API 구현
   - 공유된 채팅 조회 API 구현
   - 서비스 로직 구현

3. 프론트엔드 구현
   - API 서비스 함수 구현
   - Header.tsx에 공유하기 버튼 추가
   - 공유 페이지 컴포넌트 구현
   - 인증 미들웨어 예외 처리

4. 통합 테스트 및 디버깅
   - 전체 기능 흐름 테스트
   - 디버깅 및 문제 해결

## 유의사항
- UI는 StockEasy의 기존 디자인과 일관성을 유지
- 향후 공유 링크 만료 기능은 구현하지 않으나, 고려하여 설계
- 사용자 경험을 고려하여 버튼의 위치와 동작을 구현 
- 공유 링크를 보여주는 UI는 기존 스탁이지의 채팅 UI를 100% 동일하게 처리한다.
- 기존 스탁이지 UI는 절대 변경하지 않는다.