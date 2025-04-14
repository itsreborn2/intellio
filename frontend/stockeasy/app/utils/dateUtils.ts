// 날짜 관련 유틸리티 함수

/**
 * 날짜 문자열을 'mm/dd' 형식으로 포맷합니다.
 * @param dateString - 포맷할 날짜 문자열 (YYYY-MM-DD 또는 Date 객체가 인식할 수 있는 형식)
 * @returns 'mm/dd' 형식의 문자열 또는 에러 시 null
 */
export const formatDateMMDD = (dateString: string): string | null => {
  try {
    const date = new Date(dateString);
    if (isNaN(date.getTime())) {
      console.error('Invalid date string for formatting:', dateString);
      return null; // 잘못된 날짜 문자열 처리
    }
    const day = String(date.getDate()).padStart(2, '0');
    const month = String(date.getMonth() + 1).padStart(2, '0'); // 월은 0부터 시작
    return `${month}/${day}`; // mm/dd 형식으로 변경
  } catch (error) {
    console.error('Error formatting date:', error);
    return null;
  }
};
