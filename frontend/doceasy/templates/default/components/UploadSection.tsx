"use client"

import { useCallback, useState, useEffect } from 'react'
import { Upload, FileText, Loader2, AlertCircle, CheckCircle2, Clock } from 'lucide-react'
import { useDropzone } from 'react-dropzone'
import { useApp } from '@/contexts/AppContext'
import { Button } from 'intellio-common/components/ui/button'
import { IDocument, IUploadProgressData, IDocumentStatus } from "@/types"
import { useFileUpload } from "@/hooks/useFileUpload"
import { DocumentStatusBadge } from '@/components/DocumentStatusBadge'
import { UploadProgressDialog } from "intellio-common/components/ui/upload-progress-dialog"
import { FileUploadErrorDialog } from '@/components/FileUploadErrorDialog'

// 문서 분석 진행 상태 컴포넌트
const DocumentAnalysisProgress = ({ documents }: { documents: IDocument[] }) => {
  const processingDocs = documents.filter(doc => 
    doc.status === 'PROCESSING' || doc.status === 'PARTIAL' || doc.status === 'UPLOADING' || doc.status === 'UPLOADED'
  );
  const completedDocs = documents.filter(doc => doc.status === 'COMPLETED');
  const isMobile = useIsMobile(); // 모바일 환경 감지 훅 사용
  
  if (processingDocs.length === 0) return null;

  return (
    <div className={`fixed ${isMobile ? 'bottom-16 right-4' : 'bottom-24 right-8'} bg-white dark:bg-gray-800 shadow-lg rounded-lg ${isMobile ? 'p-3' : 'p-4'} z-50 ${isMobile ? 'max-w-[250px]' : 'max-w-xs'}`}>
      <div className="flex flex-col space-y-2">
        <h4 className={`font-semibold ${isMobile ? 'text-xs' : 'text-sm'}`}>문서 분석 진행 중</h4>
        
        <div className="space-y-1">
          <div className="flex justify-between text-xs">
            <span>진행 중:</span>
            <span className="font-medium">{processingDocs.length}</span>
          </div>
          <div className="flex justify-between text-xs">
            <span>완료:</span> 
            <span className="font-medium">{completedDocs.length}</span>
          </div>
          
          {/* 프로그레스 바 */}
          <div className="w-full bg-gray-200 rounded-full h-1.5 mt-1">
            <div 
              className="bg-blue-600 h-1.5 rounded-full transition-all duration-300"
              style={{ 
                width: `${processingDocs.length + completedDocs.length === 0 
                  ? 5 // 아직 문서 처리 전에는 5%로 표시
                  : Math.floor((completedDocs.length / 
                     (processingDocs.length + completedDocs.length)) * 100)}%` 
              }}
            ></div>
          </div>
        </div>
      </div>
    </div>
  );
};

// MIME 타입 매핑 객체를 accept와 동일한 형태로 수정
const ACCEPTED_FILE_TYPES: Record<string, readonly string[]> = {
  'application/pdf': ['.pdf'],
  'application/msword': ['.doc'],
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
  'text/plain': ['.txt'],
  'application/x-hwp': ['.hwp'],
  'application/x-hwpx': ['.hwpx'],
  'application/vnd.ms-excel': ['.xls'],
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
  'image/jpeg': ['.jpg', '.jpeg'],
  'image/png': ['.png'],
  'image/gif': ['.gif'],
  'image/tiff': ['.tiff']
} as const;

type AcceptedMimeTypes = keyof typeof ACCEPTED_FILE_TYPES;

// 확장자로 MIME 타입을 찾는 함수
function getMimeTypeFromExtension(extension: string): AcceptedMimeTypes | undefined {
  const entry = Object.entries(ACCEPTED_FILE_TYPES).find(([_, extensions]) => 
    extensions.includes(extension)
  );
  return entry ? (entry[0] as AcceptedMimeTypes) : undefined;
}

// 파일 확장자 추출 함수는 유지
function getFileExtension(filename: string): string {
  return filename.toLowerCase().match(/\.[^.]*$/)?.[0] || '';
}

// 모바일 환경 감지 훅
const useIsMobile = () => {
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const checkIsMobile = () => {
      setIsMobile(window.innerWidth < 768); // 768px 미만을 모바일로 간주
    };

    // 초기 체크
    checkIsMobile();

    // 리사이즈 이벤트에 대응
    window.addEventListener('resize', checkIsMobile);
    return () => window.removeEventListener('resize', checkIsMobile);
  }, []);

  return isMobile;
};

export const UploadSection = () => {
  const { state, dispatch } = useApp()
  const isMobile = useIsMobile(); // 모바일 환경 감지 훅 사용
  const [uploadStatus, setUploadStatus] = useState({
    total: 0,
    error: 0,
    failedFiles: [] as string[]
  })
  const { uploadProgress, uploadError, handleFileUpload, closeErrorDialog, showErrorDialog } = useFileUpload()

  const updateUploadStatus = useCallback(
    (
      total: number, 
      error: number, 
      failedFiles: string[]
    ) => {
      setUploadStatus({
        total,
        error,
        failedFiles
      })
    }, [dispatch]
  )

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    console.log('onDrop 호출됨, 파일 개수:', acceptedFiles.length);
    
    // 파일 개수 검증
    if (acceptedFiles.length === 0) {
      console.warn('업로드할 파일이 선택되지 않았습니다.');
      return;
    }
    
    if (acceptedFiles.length > 100) {
      console.warn('최대 100개까지만 업로드할 수 있습니다.');
      showErrorDialog('최대 100개까지만 업로드할 수 있습니다.');
      setUploadStatus({
        total: acceptedFiles.length,
        error: acceptedFiles.length,
        failedFiles: ['최대 100개까지만 업로드할 수 있습니다']
      });
      return;
    }

    // 파일 MIME 타입 처리 및 로깅
    const processedFiles = acceptedFiles.map(file => {
      let mimeType = file.type;
      const ext = getFileExtension(file.name);
      
      // 1. MIME 타입이 허용된 타입 목록에 있는지 확인
      const isAcceptedMimeType = Object.keys(ACCEPTED_FILE_TYPES).includes(mimeType);
      
      // 2. MIME 타입이 없거나 허용되지 않은 타입인 경우 확장자 기반으로 매핑
      if (!mimeType || !isAcceptedMimeType || mimeType === 'application/octet-stream') {
        const mappedType = getMimeTypeFromExtension(ext);
        if (mappedType) {
          mimeType = mappedType;
        } else {
          console.warn(`지원하지 않는 파일 형식입니다: ${file.name} (${file.type})`);
        }
      }

      console.log('파일 상세 정보:', {
        name: file.name,
        originalType: file.type,
        mappedType: mimeType,
        size: file.size,
        lastModified: new Date(file.lastModified).toISOString(),
        extension: ext,
        isAcceptedMimeType
      });

      // 새로운 File 객체 생성하여 MIME 타입 적용
      return new File([file], file.name, { type: mimeType });
    });
    
    await handleFileUpload(processedFiles);
  }, [handleFileUpload, showErrorDialog])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({ 
    onDrop,
    accept: ACCEPTED_FILE_TYPES,
    maxFiles: 100,
    maxSize: 40 * 1024 * 1024, // 40MB 제한 추가
    onDropRejected: (rejectedFiles) => {
      console.log('onDropRejected 호출됨:', rejectedFiles);
      
      // 다양한 오류 유형 처리
      const errorMessages: string[] = [];
      
      // 파일 개수 초과 검사
      const tooManyFiles = rejectedFiles.some(item => 
        item.errors.some(err => err.code === 'too-many-files')
      );
      
      // 파일 크기 초과 검사
      const fileSizeExceeded = rejectedFiles.some(item => 
        item.errors.some(err => err.code === 'file-too-large')
      );
      
      // 파일 타입 불일치 검사
      const fileTypeNotAccepted = rejectedFiles.some(item => 
        item.errors.some(err => err.code === 'file-invalid-type')
      );
      
      if (tooManyFiles) {
        errorMessages.push('파일 개수가 100개를 초과하였습니다.');
      }
      
      if (fileSizeExceeded) {
        errorMessages.push('파일 크기가 50MB를 초과하였습니다.');
      }
      
      if (fileTypeNotAccepted) {
        errorMessages.push('지원하지 않는 파일 형식이 포함되어 있습니다.');
      }
      
      // 오류 메시지가 있으면 상태 업데이트 및 오류 다이얼로그 표시
      if (errorMessages.length > 0) {
        setUploadStatus(prev => ({
          ...prev,
          error: prev.error + rejectedFiles.length,
          failedFiles: [...prev.failedFiles, ...errorMessages]
        }));
        
        showErrorDialog(errorMessages.join('\n'));
      }
    }
  })

  return (
    <>
      <UploadProgressDialog {...uploadProgress} />
      <FileUploadErrorDialog 
        isOpen={uploadError.isOpen}
        onClose={closeErrorDialog}
        errorMessage={uploadError.message}
      />
      <div className="w-full h-[50vh] flex items-center justify-center p-2 sm:p-4">
        <div
          {...getRootProps()}
          className={`w-full h-full max-w-4xl ${isMobile ? 'p-4 sm:p-6' : 'p-8'} rounded-lg border-2 border-dashed transition-all duration-200 flex flex-col items-center justify-center cursor-pointer
            ${isDragActive 
              ? 'border-primary bg-primary/10 scale-[0.99] shadow-lg' 
              : 'border-muted-foreground/25 hover:border-primary/50 hover:bg-primary/5'}`}
        >
          <div className="flex flex-col items-center text-center space-y-4 sm:space-y-6">
            {/* 아이콘 배경색 및 아이콘 색상 변경 */}
            <div className={`${isMobile ? 'p-4' : 'p-6'} rounded-full transition-colors duration-200 ${isDragActive ? 'bg-primary/20' : 'bg-[#282A2E]'}`}>
              <Upload className={`${isMobile ? 'w-6 h-6' : 'w-8 h-8'} transition-colors duration-200 ${isDragActive ? 'text-primary' : 'text-[#10A37F]'}`} />
            </div>
            <div className="space-y-2">
              <h3 className={`font-semibold ${isMobile ? 'text-lg' : 'text-xl'}`}>문서 업로드</h3>
              <p className={`${isMobile ? 'text-xs' : 'text-sm'} text-muted-foreground`}>
                이곳에 문서를 끌어다 놓거나 클릭하여 선택하세요
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                최대 100개 파일까지 업로드 가능
              </p>
              <p className="text-xs text-muted-foreground mt-2 max-w-full break-words">
                PDF, Word(doc/docx), 한글(hwp/hwpx), 엑셀(xls/xlsx), 이미지(jpg/jpeg/png/gif/tiff), 텍스트(txt)
              </p>
              
              <input {...getInputProps()} />

              {/* 업로드 상태 표시 */}
              {uploadStatus.total > 0 && (
                <div className="mt-4 text-sm">
                  <div className={`flex ${isMobile ? 'flex-col space-y-1' : 'items-center space-x-2'}`}>
                    <div className="text-green-600">성공: {uploadStatus.total - uploadStatus.error}</div>
                    {uploadStatus.error > 0 && (
                      <div className="text-red-600">
                        실패: {uploadStatus.error}
                        {uploadStatus.failedFiles.length > 0 && (
                          <div className="text-xs mt-1 max-w-full break-words">
                            실패한 파일: {uploadStatus.failedFiles.join(', ')}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-2 mt-2">
                    <div
                      className="bg-primary rounded-full h-2 transition-all duration-500"
                      style={{
                        width: `${((uploadStatus.total - uploadStatus.error) / uploadStatus.total) * 100}%`
                      }}
                    />
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
      <DocumentAnalysisProgress documents={Object.values(state.documents)} />
    </>
  )
}
