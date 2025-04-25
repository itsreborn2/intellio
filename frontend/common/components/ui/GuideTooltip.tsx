// 설명(가이드)용 툴팁 컴포넌트
// 디자인: 배경 #1E1F22, 글자색 흰색, 둥근 모서리, 그림자, 꼬리 포함, 제목/본문 구분
// 데스크탑: hover, 모바일: 탭/터치로 노출, 아이콘 트리거 옵션 지원

import * as React from 'react'
import * as TooltipPrimitive from '@radix-ui/react-tooltip'
import { Info } from 'lucide-react'

interface GuideTooltipProps {
  /** 툴팁 제목(굵게) */
  title: string
  /** 툴팁 본문(설명) */
  description?: string
  /** 트리거 요소(없으면 info 아이콘) */
  children?: React.ReactNode
  /** 아이콘 트리거 사용 여부 (true면 info 아이콘이 트리거) */
  withIcon?: boolean
  /** 툴팁 위치 (top, right, bottom, left) */
  side?: 'top' | 'right' | 'bottom' | 'left'
  /** 툴팁 너비 */
  width?: number | string
  /** 툴팁 충돌 감지 시 여백 (px) */
  collisionPadding?: number | Partial<Record<'top' | 'right' | 'bottom' | 'left', number>>;
}

/**
 * 설명/가이드용 툴팁 컴포넌트
 * - 데스크탑: hover, 모바일: 탭/터치로 노출
 * - 배경 #1E1F22, 흰색 글자, 그림자, 꼬리 포함
 * - 제목/본문 구분, 아이콘 트리거 옵션
 */
export function GuideTooltip({
  title,
  description,
  children,
  withIcon = false,
  side = 'top',
  width = 280,
  collisionPadding,
}: GuideTooltipProps) {
  // 모바일 환경 감지 (터치 기반)
  const [isMobile, setIsMobile] = React.useState(false)
  React.useEffect(() => {
    setIsMobile(window.matchMedia('(pointer: coarse)').matches)
  }, [])

  // 아이콘 트리거
  const trigger = withIcon || !children ? (
    <button
      type="button"
      tabIndex={0}
      aria-label="안내"
      className="inline-flex items-center justify-center w-6 h-6 rounded-full hover:bg-neutral-800/40 focus:bg-neutral-800/60 transition outline-none border-none p-0"
      style={{ color: '#fff', background: 'transparent' }}
    >
      <Info size={18} />
    </button>
  ) : (
    children
  )

  return (
    <TooltipPrimitive.Provider delayDuration={100} skipDelayDuration={200}>
      <TooltipPrimitive.Root>
        <TooltipPrimitive.Trigger asChild>
          {/* 트리거: 아이콘 또는 children */}
          {trigger}
        </TooltipPrimitive.Trigger>
        <TooltipPrimitive.Portal>
          <TooltipPrimitive.Content
            side={side}
            align="center"
            sideOffset={10}
            collisionPadding={collisionPadding}
            // 모바일: 클릭/터치로 열고 외부 클릭 시 닫힘
            // 데스크탑: hover로 열림
            className="z-50"
          >
            <div
              className="relative"
              style={{ width: typeof width === 'number' ? `${width}px` : width }}
            >
              {/* 툴팁 본체 */}
              <div
                className="rounded-xl shadow-xl px-4 py-3"
                style={{
                  background: '#1E1F22',
                  color: '#fff',
                  boxShadow: '0 6px 32px 0 rgba(0,0,0,0.18)',
                  fontSize: '14px',
                  lineHeight: 1.5,
                }}
              >
                <div className="font-semibold mb-1" style={{ fontSize: '15px' }}>{title}</div>
                {/* description이 문자열이면 \n을 <br />로 변환, JSX면 그대로 렌더 */}
{description && (
  <div className="text-sm text-neutral-200" style={{ fontWeight: 400 }}>
    {typeof description === 'string'
      ? description.split(/\r?\n/).map((line, idx, arr) =>
          idx < arr.length - 1 ? (
            <React.Fragment key={idx}>{line}<br /></React.Fragment>
          ) : (
            <React.Fragment key={idx}>{line}</React.Fragment>
          )
        )
      : description}
  </div>
)}
              </div>
              {/* 꼬리(arrow) */}
              <TooltipPrimitive.Arrow
                className=""
                width={20}
                height={10}
                style={{ fill: '#1E1F22', filter: 'drop-shadow(0 2px 8px rgba(0,0,0,0.12))' }}
              />
            </div>
          </TooltipPrimitive.Content>
        </TooltipPrimitive.Portal>
      </TooltipPrimitive.Root>
    </TooltipPrimitive.Provider>
  )
}

/*
사용 예시:
<GuideTooltip title="이건 뭐죠?" description="여기에 대한 자세한 설명입니다.">
  <span>여기를 설명</span>
</GuideTooltip>

<GuideTooltip title="이건 뭐죠?" description="여기에 대한 자세한 설명입니다." withIcon />
*/
