/**
 * styleUtils.ts
 * 스타일 관련 유틸리티 함수 및 상수
 */
import { CSSProperties } from 'react';

// 사이드바 너비 상수 (픽셀 단위)
export const SIDEBAR_WIDTH = 59;

/**
 * 반응형 폰트 크기 계산
 * @param isMobile 모바일 여부
 * @param windowWidth 창 너비
 * @param mobileSize 모바일 크기
 * @param tabletSize 태블릿 크기
 * @param desktopSize 데스크탑 크기
 * @returns 계산된 폰트 크기
 */
export function getResponsiveFontSize(
  isMobile: boolean,
  windowWidth: number,
  mobileSize: string,
  tabletSize: string,
  desktopSize: string
): string {
  if (isMobile) return mobileSize;
  return windowWidth < 768 ? tabletSize : desktopSize;
}

/**
 * 반응형 패딩 계산
 * @param isMobile 모바일 여부
 * @param windowWidth 창 너비
 * @param mobileSize 모바일 크기
 * @param tabletSize 태블릿 크기
 * @param desktopSize 데스크탑 크기
 * @returns 계산된 패딩 크기
 */
export function getResponsivePadding(
  isMobile: boolean,
  windowWidth: number,
  mobileSize: string,
  tabletSize: string,
  desktopSize: string
): string {
  if (isMobile) return mobileSize;
  return windowWidth < 768 ? tabletSize : desktopSize;
}

/**
 * 반응형 너비 계산
 * @param isMobile 모바일 여부
 * @param windowWidth 창 너비
 * @returns 계산된 너비 (백분율)
 */
export function getResponsiveWidth(isMobile: boolean, windowWidth: number): string {
  if (isMobile) return '100%';
  if (windowWidth < 768) return '95%';
  if (windowWidth < 1024) return '85%';
  return '70%';
}

/**
 * 마크다운 스타일 생성
 * @param isMobile 모바일 여부
 * @param windowWidth 창 너비
 * @returns 마크다운용 CSS 스타일 문자열
 */
export function getMarkdownStyles(isMobile: boolean, windowWidth: number): string {
  return `
    .markdown-content {
      font-size: ${isMobile ? '0.9rem' : (windowWidth < 768 ? '0.95rem' : '1rem')};
      line-height: 1.6;
      max-width: 100%;
      overflow-wrap: break-word;
      word-wrap: break-word;
    }
    .markdown-content p {
      margin-top: 0.5em;
      margin-bottom: 1em;
      white-space: pre-line;
      max-width: 100%;
    }
    .markdown-content ul, .markdown-content ol {
      margin-top: 0.5em;
      margin-bottom: 1em;
      padding-left: 1.5em;
    }
    .markdown-content li {
      margin-top: 0;
      margin-bottom: 0;
      line-height: 1.3;
      padding-bottom: 0;
      white-space: normal;
    }
    .markdown-content li p {
      margin-top: 0;
      margin-bottom: 0;
      white-space: pre-line;
    }
    .markdown-content li + li {
      margin-top: 0;
    }
    .markdown-content h1, .markdown-content h2, .markdown-content h3, .markdown-content h4 {
      margin-top: 1.5em;
      margin-bottom: 1em;
      line-height: 1.3;
    }
    .markdown-content blockquote {
      margin-left: 0;
      padding-left: 1em;
      border-left: 3px solid #ddd;
      color: #555;
      margin-top: 1em;
      margin-bottom: 1em;
      white-space: pre-line;
    }
  `;
}

/**
 * 메시지 영역 컨테이너 스타일 계산
 * @param isMobile 모바일 여부
 * @param windowWidth 창 너비
 * @param isInputCentered 입력창 중앙 정렬 여부
 * @returns 메시지 컨테이너 스타일 객체
 */
export function getMessagesContainerStyle(
  isMobile: boolean,
  windowWidth: number,
  isInputCentered: boolean
): CSSProperties {
  return {
    overflowY: 'auto',
    overflowX: 'hidden',
    paddingTop: isMobile ? '10px' : (windowWidth < 768 ? '15px' : '20px'),
    paddingRight: isMobile ? '5px' : (windowWidth < 768 ? '8px' : '10px'),
    paddingBottom: isInputCentered ? (isMobile ? '10px' : (windowWidth < 768 ? '15px' : '20px')) : (isMobile ? '80px' : '90px'),
    paddingLeft: isMobile ? '5px' : (windowWidth < 768 ? '8px' : '10px'),
    margin: '0 auto',
    border: 'none',
    borderRadius: '0',
    backgroundColor: '#F4F4F4',
    width: getResponsiveWidth(isMobile, windowWidth),
    height: '100%',
    minHeight: 'calc(100% - 60px)',
    boxSizing: 'border-box',
    position: 'relative',
    display: isInputCentered ? 'none' : 'block',
    opacity: 1,
    maxWidth: '100%',
  };
}

/**
 * 입력 영역 스타일 계산
 * @param isMobile 모바일 여부
 * @param windowWidth 창 너비
 * @param isInputCentered 입력창 중앙 정렬 여부
 * @returns 입력 영역 스타일 객체
 */
export function getInputAreaStyle(
  isMobile: boolean,
  windowWidth: number,
  isInputCentered: boolean
): CSSProperties {
  return {
    width: '100%',
    marginTop: isInputCentered ? (isMobile ? '25vh' : (windowWidth < 768 ? '30vh' : '35vh')) : '0px',
    marginBottom: '5px',
    position: isInputCentered ? 'relative' : 'fixed',
    bottom: isInputCentered ? 'auto' : '0',
    left: isInputCentered ? '0' : (!isMobile ? `calc(50% - ${1037 / 2}px + ${SIDEBAR_WIDTH / 2}px)` : '0'),
    zIndex: 100,
    backgroundColor: isInputCentered ? 'transparent' : '#F4F4F4',
    maxWidth: isInputCentered ? '100%' : (!isMobile ? `1037px` : '100%'),
    paddingBottom: '5px'
  };
} 