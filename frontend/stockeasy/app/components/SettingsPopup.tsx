'use client'

import { useState, useEffect } from 'react'
import { X, User, PaintBucket, Settings, LogOut, Clock, MessageSquare } from 'lucide-react'
import axios from 'axios'
import Image from 'next/image'
import { Avatar, AvatarImage, AvatarFallback } from "intellio-common/components/ui/avatar"
import { logout } from '../utils/auth'
import { useTokenUsageStore } from '@/stores/tokenUsageStore'
import { useQuestionCountStore } from '@/stores/questionCountStore'

interface SettingsPopupProps {
  isOpen: boolean;
  onClose: () => void;
  userId?: string | null;
  userName?: string;
  userEmail?: string;
  userProvider?: string;
  userImage?: string;
}

type TabType = '계정' | '외형' | '맞춤 설정';
type PeriodType = 'day' | 'week' | 'month' | 'year';

export default function SettingsPopup({ isOpen, onClose, userId, userName, userEmail, userProvider, userImage }: SettingsPopupProps) {
  const [email, setEmail] = useState<string>(userEmail || '');
  const [name, setName] = useState<string>('기사 장');
  const [profileImage, setProfileImage] = useState<string | null>(null);
  const [provider, setProvider] = useState<string>('');
  const [activeTab, setActiveTab] = useState<TabType>('계정');
  const [isLoaded, setIsLoaded] = useState<boolean>(false);
  const [period, setPeriod] = useState<PeriodType>('month');
  
  // 토큰 사용량 스토어 사용
  const { summary, fetchSummary, isLoading } = useTokenUsageStore();
  
  // 질문 개수 스토어 사용
  const { 
    summary: questionSummary, 
    fetchSummary: fetchQuestionSummary, 
    isLoading: isQuestionLoading 
  } = useQuestionCountStore();
  
  // 컴포넌트 마운트 시 사용자 정보 로드
  useEffect(() => {
    // 이메일 정보 설정
    if (userEmail) {
      setEmail(userEmail);
    }
    
    if (userName) {
      setName(userName);
    }
    
    if (userProvider) {
      setProvider(userProvider);
    }
    
    if (userImage) {
      setProfileImage(userImage);
    }
    
    // 모든 상태가 설정된 후 로드 완료 표시
    setIsLoaded(true);
  }, [userEmail, userName, userProvider, userImage]);
  
  // 팝업이 열릴 때 토큰 사용량 정보와 질문 개수 정보 가져오기
  useEffect(() => {
    if (isOpen) {
      fetchSummary('stockeasy', period);
      fetchQuestionSummary('day', 'day');
    }
  }, [isOpen, period, fetchSummary, fetchQuestionSummary]);
  
  // 기간 변경 시 토큰 사용량 정보와 질문 개수 정보 다시 가져오기
  const handlePeriodChange = (newPeriod: PeriodType) => {
    setPeriod(newPeriod);
    fetchSummary('stockeasy', newPeriod);
    fetchQuestionSummary('day', 'day');
  };
  
  // 사용자 이름의 첫 글자 또는 이니셜 가져오기
  const getInitials = () => {
    if (!name) return '?';
    const words = name.split(' ');
    if (words.length >= 2) {
      return `${words[0][0]}${words[1][0]}`.toUpperCase();
    }
    return name[0].toUpperCase();
  };
  
  // 이메일 기반으로 일관된 배경색 생성
  const getProfileBgColor = () => {
    if (!email) return 'bg-orange-500';
    
    // 간단한 해시 함수로 이메일에서 색상 생성
    const hash = email.split('').reduce((acc: number, char: string) => {
      return char.charCodeAt(0) + ((acc << 5) - acc);
    }, 0);
    
    // 미리 정의된 색상 배열
    const colors = [
      'bg-red-500', 'bg-orange-500', 'bg-amber-500', 'bg-yellow-500',
      'bg-lime-500', 'bg-green-500', 'bg-emerald-500', 'bg-teal-500',
      'bg-cyan-500', 'bg-sky-500', 'bg-blue-500', 'bg-indigo-500',
      'bg-violet-500', 'bg-purple-500', 'bg-fuchsia-500', 'bg-pink-500'
    ];
    
    // 해시값을 사용하여 색상 배열에서 색상 선택
    return colors[Math.abs(hash) % colors.length];
  };
  
  // 로그아웃 처리 함수
  const handleLogout = async () => {
    try {
      // 확인 메시지 표시
      if (confirm('로그아웃 하시겠습니까?')) {
        await logout();
      }
    } catch (error) {
      console.error('로그아웃 중 오류 발생:', error);
      alert('로그아웃 처리 중 오류가 발생했습니다.');
    }
  };
  
  // 숫자 포맷 함수
  const formatNumber = (num: number | undefined | null) => {
    if (num === undefined || num === null) {
      return '0';
    }
    return num.toLocaleString('ko-KR');
  };
  
  // 비용 포맷 함수
  const formatCost = (cost: number | undefined | null) => {
    if (cost === undefined || cost === null) {
      return '0';
    }
    return cost.toLocaleString('ko-KR', { maximumFractionDigits: 6 });
  };
  
  // 날짜 포맷 함수
  const formatDate = (dateString: string | undefined | null) => {
    if (!dateString) {
      return '날짜 정보 없음';
    }
    try {
      const date = new Date(dateString);
      if (isNaN(date.getTime())) {
        return '유효하지 않은 날짜';
      }
      return date.toLocaleDateString('ko-KR', { 
        year: 'numeric', 
        month: 'long', 
        day: 'numeric' 
      });
    } catch (error) {
      return '날짜 변환 오류';
    }
  };
  
  // 기간 이름 반환 함수
  const getPeriodName = (periodType: PeriodType) => {
    switch(periodType) {
      case 'day': return '오늘';
      case 'week': return '이번 주';
      case 'month': return '이번 달';
      case 'year': return '올해';
      default: return '오늘';
    }
  };
  
  if (!isOpen) return null;
  
  const tabIcons = {
    '계정': <User className="w-5 h-5 mr-2" />,
    '외형': <PaintBucket className="w-5 h-5 mr-2" />,
    '맞춤 설정': <Settings className="w-5 h-5 mr-2" />
  };
  
  const renderTabContent = () => {
    switch(activeTab) {
      case '계정':
        return (
          <div className="space-y-6">
            {/* 프로필 영역 */}
            <div className="flex items-start">
              <div className="mr-4">
                {/* 컴포넌트가 완전히 로드된 후에만 아바타 표시 */}
                {isLoaded && (
                  profileImage && !profileImage.includes('googleusercontent.com') ? (
                    <Avatar className="w-16 h-16">
                      <AvatarImage src={profileImage} alt={name || '사용자'} />
                      <AvatarFallback className="bg-gray-700 text-gray-100 text-lg">
                        {getInitials()}
                      </AvatarFallback>
                    </Avatar>
                  ) : (
                    <Avatar className="w-16 h-16">
                      <AvatarFallback className="bg-gray-700 text-gray-100 text-lg">
                        {getInitials()}
                      </AvatarFallback>
                    </Avatar>
                  )
                )}
              </div>
              <div className="flex-1">
                <div className="flex items-center justify-between">
                  <div>
                    {/* 사용자 이름 폰트 크기 조정 */}
                    <p className="font-medium">{name || '사용자'}</p> 
                    <p className="text-sm text-gray-500">{email}</p>
                  </div>
                </div>
              </div>
            </div>

            {/* 질문 개수 정보 섹션 */}
            <div className="border-t pt-4">
              {/* 제목 폰트 크기 조정 */}
              <h3 className="font-medium mb-3 flex items-center text-base"> 
                <MessageSquare className="w-4 h-4 mr-2" />
                질문 개수 정보
              </h3>
              
              {/* 기간 선택 탭 */}
              <div className="flex mb-4 border-b">
                {(['day'] as PeriodType[]).map((p) => (
                  <button
                    key={p}
                    className={`px-4 py-2 text-sm ${period === p 
                      ? 'border-b-2 border-blue-500 text-blue-500 font-medium' 
                      : 'text-gray-500 hover:text-gray-700'}`}
                    onClick={() => handlePeriodChange(p)}
                  >
                    {getPeriodName(p)}
                  </button>
                ))}
              </div>
              
              {/* 질문 개수 표시 */}
              {isQuestionLoading ? (
                <div className="flex justify-center items-center py-4">
                  <div className="loader"></div>
                </div>
              ) : questionSummary ? (
                <div className="space-y-4">
                  <div className="text-sm text-gray-500 mb-2">
                    {formatDate(questionSummary.start_date)} ~ {formatDate(questionSummary.end_date)}
                  </div>
                  
                  {/* 요약 정보 */}
                  <div className="bg-gray-50 p-4 rounded-lg">
                    {/* 제목 폰트 크기 조정 */}
                    <h4 className="font-medium mb-2 text-base">총 질문</h4> 
                    {/* 값 폰트 크기 조정 */}
                    <div className="font-medium"> 
                      {isQuestionLoading ? (
                        '로딩 중...'
                      ) : (
                        `${formatNumber(questionSummary?.total_questions)} / 100`
                      )}
                    </div>
                  </div>
                  
                 
                </div>
              ) : (
                <div className="text-gray-500 py-4">
                  질문 개수 정보를 가져올 수 없습니다.
                </div>
              )}
            </div>

            
          </div>
        );
      case '외형':
        return (
          <div className="space-y-4">
            <h3 className="font-medium mb-2">테마 설정</h3>
            <div className="flex items-center justify-between border-b pb-4">
              <span>테마 모드</span>
              <select className="border rounded p-1">
                <option>라이트</option>
                <option>다크</option>
                <option>시스템 설정</option>
              </select>
            </div>
            <div className="pt-2">
              <span>폰트 크기</span>
              <div className="mt-2 flex items-center gap-2">
                <input 
                  type="range" 
                  min="12" 
                  max="20" 
                  className="w-full"
                />
              </div>
            </div>
          </div>
        );
      case '맞춤 설정':
        return (
          <div className="space-y-4">
            <h3 className="font-medium mb-2">알림 설정</h3>
            <div className="flex items-center justify-between border-b pb-4">
              <span>이메일 알림</span>
              <input type="checkbox" className="toggle" />
            </div>
            <div className="flex items-center justify-between border-b pb-4">
              <span>데이터 컨트롤</span>
              <button className="text-blue-500 px-3 py-1 text-sm rounded-full border border-blue-500">
                변경
              </button>
            </div>
          </div>
        );
      default:
        return null;
    }
};
  
  return (
    // Modal overlay
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-[20000] p-4" onClick={onClose}>
      {/* Modal Content container - responsive width and height */}
      <div 
        className="bg-white dark:bg-gray-800 shadow-lg rounded-xl overflow-hidden w-full max-w-md h-auto max-h-[90vh] flex flex-col md:w-[800px] md:h-[600px] md:max-h-[90vh]"
        // Removed inline style: {{ width: '800px', height: '600px', marginLeft: '59px' }}
        onClick={(e) => e.stopPropagation()} // Prevent closing modal when clicking inside
      >
        {/* Header */}
        <div className="flex justify-between items-center px-4 py-3 md:px-6 md:py-4 border-b flex-shrink-0">
          <h1 className="text-lg font-medium">설정</h1>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-700">
            <X size={20} />
          </button>
        </div>
        
        {/* Main content area - responsive direction */}
        <div className="flex flex-col md:flex-row flex-grow overflow-hidden"> 
          {/* Left tab menu - responsive width and borders */}
          <div className="w-full md:w-1/4 border-b md:border-b-0 md:border-r flex-shrink-0">
            <ul>
              {/* Currently only '계정' tab is active */} 
              {(['계정'] as TabType[]).map((tab) => (
                <li key={tab}>
                  <button
                    className={`flex items-center w-full text-left px-4 py-3 md:px-6 md:py-4 ${
                      activeTab === tab 
                        ? 'bg-gray-100 dark:bg-gray-700 font-medium' 
                        : 'hover:bg-gray-50 dark:hover:bg-gray-700'
                    }`}
                    onClick={() => setActiveTab(tab)}
                  >
                    {/* Tab icon rendering needs review if more tabs are added */}
                    {tab === '계정' && <User size={20} className="mr-2" />} 
                    {tab}
                  </button>
                </li>
              ))}
            </ul>
          </div>
          
          {/* Right content area - responsive padding and scrolling */}
          <div className="flex-1 p-4 md:p-6 overflow-y-auto">
            {renderTabContent()} 
          </div>
        </div>
      </div>
    </div>
  );
} 