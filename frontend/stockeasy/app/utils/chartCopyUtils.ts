import { toPng } from 'html-to-image';

interface CopyChartOptions {
  copyrightText?: string;
  scale?: number;
  backgroundColor?: string;
  watermark?: {
    text?: string;
    opacity?: number;
    fontSize?: string;
    color?: string;
  };
}

/**
 * 차트 복사 버튼 컴포넌트 속성 타입
 */
export interface ChartCopyButtonProps {
  chartRef: React.RefObject<HTMLDivElement>;
  chartName: string;
  options?: CopyChartOptions;
  className?: string;
  buttonText?: string;
  updateDateText?: string;
  /**
   * 캡처(복사) 시작 시 호출되는 콜백
   */
  onStartCapture?: () => void;
  /**
   * 캡처(복사) 종료(성공/실패 포함) 시 호출되는 콜백
   */
  onEndCapture?: () => void;
}

/**
 * 차트를 이미지로 복사하는 유틸리티 함수
 * @param chartRef 차트 요소에 대한 참조
 * @param chartName 차트 이름 (알림 메시지에 사용)
 * @param options 추가 옵션 (저작권 텍스트 등)
 * @param updateDateText 차트 컴포넌트에서 전달받은 업데이트 날짜/시간 텍스트
 */
export const copyChartAsImage = async (
  chartRef: React.RefObject<HTMLDivElement>,
  chartName: string,
  options?: CopyChartOptions,
  updateDateText?: string
) => {
  // 로딩 메시지 즉시 표시
  const loadingToast = document.createElement('div');
  loadingToast.className = 'fixed top-4 right-4 bg-blue-600 text-white px-4 py-2 rounded shadow-lg z-50 animate-pulse';
  loadingToast.innerHTML = '<strong>이미지 생성 중...</strong>';
  document.body.appendChild(loadingToast);
  await new Promise(resolve => setTimeout(resolve, 0));

  if (!chartRef.current) {
    document.body.removeChild(loadingToast);
    alert('차트 참조가 올바르지 않습니다.');
    return;
  }

  // 기본 옵션 설정
  const defaultOptions: CopyChartOptions = {
    copyrightText: '',
    scale: 2,
    backgroundColor: '#ffffff',
    watermark: {
      // 테이블 복사와 동일한 워터마크 텍스트, 더 큰 영역에 맞춰 폰트 크기 증가
      text: '스탁이지\nby (주)인텔리오\nhttps://intellio.kr',
      opacity: 0.08, // 8% 불투명도(매우 흐림)
      fontSize: '36px', // 차트 영역이 크므로 더 크게
      color: '#000000'
    }
  };
  const mergedOptions = { ...defaultOptions, ...options };

  // 이미지 생성 전: 복사 버튼 숨김 처리
  const copyButtons = chartRef.current?.querySelectorAll('.chart-copy-btn');
  copyButtons?.forEach(btn => (btn as HTMLElement).style.visibility = 'hidden');

  try {
    // 차트 캡처
    const dataUrl = await toPng(chartRef.current, {
      backgroundColor: mergedOptions.backgroundColor,
      cacheBust: true,
      pixelRatio: mergedOptions.scale || 2,
      skipFonts: true, // SecurityError 우회: 외부 폰트 임베딩을 건너뜀
      // style 병합 부분 제거 (타입 에러 방지)
      ...mergedOptions,
    }); // skipFonts: true 옵션 추가

    // 이미지 객체 생성
    const img = new window.Image();
    img.src = dataUrl;
    img.onload = () => {
      // 워터마크/저작권 추가 (캔버스에 직접 그리기)
      const canvas = document.createElement('canvas');
      canvas.width = img.width;
      canvas.height = img.height + (mergedOptions.copyrightText ? 24 : 0); // 저작권 영역 추가
      const ctx = canvas.getContext('2d');
      if (!ctx) return;
      ctx.drawImage(img, 0, 0);
      // 워터마크: 차트 전체 영역에 대각선으로 크게 반복 표시
      if (mergedOptions.watermark?.text) {
        ctx.save();
        ctx.globalAlpha = mergedOptions.watermark.opacity || 0.08;
        // 폰트 크기: 차트 크기에 따라 유동적으로 조정(최소 36px, 최대 7vw)
        // 폰트 크기: 차트 크기에 따라 더 작게(30% 추가 축소)
        const fontSize = Math.max(canvas.width, canvas.height) / 36;
        ctx.font = `${fontSize}px Arial`;
        ctx.fillStyle = mergedOptions.watermark.color || '#000000';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        // 차트 중앙에 한 번만 대각선 워터마크 표시 (줄바꿈 지원)
        ctx.save();
        ctx.translate(canvas.width / 2, canvas.height / 2);
        ctx.rotate(-Math.PI / 6); // -30도 대각선
        const lines = (mergedOptions.watermark.text || '').split('\n');
        const lineHeight = fontSize * 1.25;
        const totalHeight = lineHeight * lines.length;
        lines.forEach((line, i) => {
          ctx.fillText(line, 0, (i - (lines.length - 1) / 2) * lineHeight);
        });
        ctx.restore();
      }
      // 저작권 텍스트
      if (mergedOptions.copyrightText) {
        ctx.save();
        ctx.globalAlpha = 1;
        ctx.font = 'bold 10px Arial';
        ctx.fillStyle = '#666';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'bottom';
        ctx.fillText(mergedOptions.copyrightText, canvas.width / 2, canvas.height - 4);
        ctx.restore();
      }
      // 업데이트 날짜 텍스트
      if (updateDateText) {
        ctx.save();
        ctx.globalAlpha = 1;
        ctx.font = 'bold 10px Arial';
        ctx.fillStyle = '#666';
        ctx.textAlign = 'right';
        ctx.textBaseline = 'top';
        ctx.fillText(updateDateText, canvas.width - 8, 8);
        ctx.restore();
      }
      // 클립보드 복사
      canvas.toBlob(blob => {
        if (blob) {
          const item = new window.ClipboardItem({ 'image/png': blob });
          navigator.clipboard.write([item]);
        }
      }, 'image/png');
      // 다운로드도 가능하게 하려면 아래 코드 사용
      // const link = document.createElement('a');
      // link.href = canvas.toDataURL('image/png');
      // link.download = `${chartName || 'chart'}.png`;
      // link.click();
    };
  } catch (error) {
    alert('차트 이미지 복사에 실패했습니다. 콘솔을 확인해주세요.');
    console.error('차트 이미지 복사 오류:', error);
  } finally {
    // 이미지 생성 후 복사 버튼 다시 보이게
    copyButtons?.forEach(btn => (btn as HTMLElement).style.visibility = 'visible');
    setTimeout(() => {
      document.body.removeChild(loadingToast);
    }, 1200);
  }
};
