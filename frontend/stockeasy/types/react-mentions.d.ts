/**
 * react-mentions 타입 선언 파일
 * 이 파일은 react-mentions 라이브러리에 대한 타입 정의를 제공합니다.
 * 기본적인 사용 방식에 맞게 간단하게 정의합니다.
 */

declare module 'react-mentions' {
  import * as React from 'react';

  // MentionsInput 컴포넌트 props 타입
  export interface MentionsInputProps extends React.InputHTMLAttributes<HTMLTextAreaElement> {
    value: string;
    onChange: (event: { target: { value: string } }) => void;
    placeholder?: string;
    singleLine?: boolean;
    className?: string;
    style?: any;
    allowSpaceInQuery?: boolean;
    children: React.ReactNode;
  }

  // Mention 컴포넌트 props 타입
  export interface MentionProps {
    trigger: string;
    data: any[] | ((query: string, callback: (data: any[]) => void) => void);
    renderSuggestion?: (
      suggestion: any,
      search: string,
      highlightedDisplay: React.ReactNode,
      index: number,
      focused: boolean
    ) => React.ReactNode;
    markup?: string;
    displayTransform?: (id: string, display: string) => string;
    regex?: RegExp;
    onAdd?: (id: string, display: string) => void;
    style?: any;
    className?: string;
    appendSpaceOnAdd?: boolean;
  }

  // 컴포넌트 선언
  export const MentionsInput: React.FC<MentionsInputProps>;
  export const Mention: React.FC<MentionProps>;
}
