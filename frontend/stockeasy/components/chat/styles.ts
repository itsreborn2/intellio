import { CSSProperties } from 'react';

// 컨테이너 너비 계산 함수
export const getContentWidth = (isMobile: boolean, windowWidth: number): string => {
  if (isMobile) return '100%';
  if (windowWidth < 768) return '95%';
  if (windowWidth < 1024) return '85%';
  return '70%';
};

// 기본 채팅 영역 스타일
export const createChatAreaStyle = (isMobile: boolean): CSSProperties => ({
  display: 'flex',
  flexDirection: 'column',
  height: '100%',
  width: '100%',
  position: 'relative',
  backgroundColor: '#F4F4F4',
  overflow: 'hidden',
  paddingTop: isMobile ? '0' : '10px',
  paddingBottom: isMobile ? '0' : '10px',
  paddingRight: isMobile ? '0' : '0px',
  paddingLeft: isMobile ? '0' : '0px',
  opacity: 1,
  fontSize: isMobile ? '14px' : undefined,
});

// 메시지 컨테이너 스타일
export const createMessagesContainerStyle = (
  isMobile: boolean, 
  windowWidth: number, 
  isInputCentered: boolean,
  transitionInProgress: boolean
): CSSProperties => ({
  flex: '1 1 auto',
  overflowY: 'auto',
  overflowX: 'hidden',
  paddingTop: isMobile ? '5px' : (windowWidth < 768 ? '8px' : '10px'),
  paddingRight: isMobile ? '5px' : (windowWidth < 768 ? '8px' : '10px'),
  paddingBottom: isMobile ? '5px' : (windowWidth < 768 ? '8px' : '10px'),
  paddingLeft: isMobile ? '5px' : (windowWidth < 768 ? '8px' : '10px'),
  margin: '0 auto',
  border: 'none',
  borderRadius: '0',
  backgroundColor: '#F4F4F4',
  width: getContentWidth(isMobile, windowWidth),
  minHeight: '0',
  boxSizing: 'border-box',
  position: 'relative',
  display: isInputCentered ? 'none' : 'block',
  opacity: transitionInProgress ? 0 : 1,
  transition: 'opacity 0.3s ease-in-out',
  maxWidth: '100%'
});

// 입력 영역 스타일
export const createInputAreaStyle = (
  isMobile: boolean, 
  windowWidth: number, 
  isInputCentered: boolean
): CSSProperties => ({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  width: '100%',
  margin: '0 auto',
  padding: '10px 0',
  boxSizing: 'border-box',
  marginTop: isInputCentered ? (isMobile ? '25vh' : (windowWidth < 768 ? '30vh' : '35vh')) : '0px',
  marginLeft: 'auto',
  marginRight: 'auto',
  //position: isInputCentered ? 'relative' : 'sticky',
  position: isInputCentered ? 'relative' : 'fixed',
  bottom: isInputCentered ? 'auto' : '0',
  left: isInputCentered ? 'auto' : '59px',
  right: '0',
  zIndex: 10,
  backgroundColor: '#F4F4F4',
  borderTop: isInputCentered ? 'none' : '1px solid #E5E7EB',
  maxWidth: isMobile ? '100%' : '70%',
  flex: '0 0 auto',
  transition: 'all 0.3s ease-in-out'
});

// 마크다운 스타일
export const getMarkdownStyles = (isMobile: boolean, windowWidth: number): string => `
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