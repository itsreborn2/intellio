/**
 * 시간 제한 관련 유틸리티 함수들
 */

interface ITimeRestriction {
  startHour: number;
  startMinute: number;
  endHour: number;
  endMinute: number;
}

// 제한 시간대 정의
const RESTRICTED_TIME_PERIODS: ITimeRestriction[] = [
  { startHour: 3, startMinute: 38, endHour: 4, endMinute: 5 },
  { startHour: 11, startMinute: 58, endHour: 12, endMinute: 5 },
  { startHour: 17, startMinute: 58, endHour: 18, endMinute: 5 },
];

/**
 * 현재 시간이 제한 시간대인지 확인하는 함수
 * Production 환경에서만 시간 제한을 적용합니다.
 * @returns {object} { isRestricted: boolean, nextAvailableTime: string }
 */
export function checkTimeRestriction(): { isRestricted: boolean; nextAvailableTime: string } {
  // Production 환경이 아닌 경우 시간 제한을 적용하지 않음
  if (process.env.NODE_ENV !== 'production') {
    return {
      isRestricted: false,
      nextAvailableTime: ''
    };
  }

  const now = new Date();
  const currentHour = now.getHours();
  const currentMinute = now.getMinutes();
  
  for (const period of RESTRICTED_TIME_PERIODS) {
    // 시작 시간과 종료 시간을 분 단위로 변환
    const startTimeInMinutes = period.startHour * 60 + period.startMinute;
    const endTimeInMinutes = period.endHour * 60 + period.endMinute;
    const currentTimeInMinutes = currentHour * 60 + currentMinute;
    
    // 현재 시간이 제한 시간대에 포함되는지 확인
    if (currentTimeInMinutes >= startTimeInMinutes && currentTimeInMinutes <= endTimeInMinutes) {
      // 다음 이용 가능 시간 포맷팅 (시:분)
      const nextAvailableTime = `${period.endHour.toString().padStart(2, '0')}:${period.endMinute.toString().padStart(2, '0')}`;
      
      return {
        isRestricted: true,
        nextAvailableTime
      };
    }
  }
  
  return {
    isRestricted: false,
    nextAvailableTime: ''
  };
}

/**
 * 제한 시간대 메시지를 생성하는 함수
 * @param nextAvailableTime 다음 이용 가능 시간
 * @returns 제한 메시지
 */
export function getRestrictionMessage(nextAvailableTime: string): string {
  return `현재 점검 중입니다. ${nextAvailableTime} 이후에 다시 질문해주세요.`;
} 