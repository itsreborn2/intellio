import os
from typing import Optional
import io
import logging
from common.core.config import settings
import tempfile
from tika import parser
import tika
tika.initVM()  # Tika 서버를 미리 초기화

logger = logging.getLogger(__name__)

class DocumentExtractor:
    """문서에서 텍스트를 추출하는 클래스"""

    def __init__(self):
        """DocumentExtractor 초기화"""
        self.document_client = None
        self.vision_client = None
        self.processor_name = f"projects/{settings.GOOGLE_CLOUD_PROJECT}/locations/us/processors/{settings.GOOGLE_DOCUMENT_AI_PROCESSOR_ID}"
        # Tika 서버 설정
        

    def _init_document_ai(self):
        """Document AI 클라이언트 초기화 (필요할 때만)"""
        if self.document_client is None:
            from google.cloud import documentai
            self.document_client = documentai.DocumentProcessorServiceClient()

    def _init_vision_ai(self):
        """Vision AI 클라이언트 초기화 (필요할 때만)"""
        if self.vision_client is None:
            from google.cloud import vision
            from google.oauth2 import service_account
            import json
            
            # settings에서 서비스 계정 키 정보 가져오기
            credentials_info = json.loads(settings.GOOGLE_CLOUD_CREDENTIALS)
            credentials = service_account.Credentials.from_service_account_info(credentials_info)
            self.vision_client = vision.ImageAnnotatorClient(credentials=credentials)

    def extract_text(self, content: bytes, mime_type: str) -> Optional[str]:
        """파일 타입에 따라 적절한 추출 방법을 선택합니다."""
        
        if mime_type in ['application/x-hwp', 'application/x-hwpx']:
            return self.extract_from_hwp(content)
        
        extractors = {
            'text/plain': self.extract_from_text,
            'application/pdf': self.extract_from_pdf,
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document': self.extract_from_docx,
            'application/msword': self.extract_from_doc,
            'application/rtf': self.extract_from_doc,  # RTF 파일도 doc 처리기로 처리
            'text/rtf': self.extract_from_doc,  # RTF의 다른 MIME 타입도 처리
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': self.extract_from_excel,
            'application/vnd.ms-excel': self.extract_from_excel,
            'image/jpeg': self.extract_from_image,
            'image/png': self.extract_from_image,
            'image/gif': self.extract_from_image,
            'image/bmp': self.extract_from_image,
            'image/tiff': self.extract_from_image,
            'image/webp': self.extract_from_image,
        }
        
        extractor = extractors.get(mime_type)
        if not extractor:
            logger.warning(f"지원하지 않는 파일 형식: {mime_type}")
            return None
            
        try:
            return extractor(content)
        except Exception as e:
            logger.error(f"텍스트 추출 실패 ({mime_type}): {str(e)}")
            raise RuntimeError(f"텍스트 추출 실패 ({mime_type}): {str(e)}")
    
    @staticmethod
    def extract_from_text(file_content: bytes) -> str:
        """일반 텍스트 파일에서 텍스트 추출"""
        try:
            return file_content.decode('utf-8').strip()
        except UnicodeDecodeError:
            try:
                return file_content.decode('cp949').strip()
            except UnicodeDecodeError:
                # 다른 인코딩도 시도
                try:
                    return file_content.decode('euc-kr').strip()
                except UnicodeDecodeError:
                    try:
                        return file_content.decode('latin1').strip()
                    except UnicodeDecodeError:
                        raise ValueError("텍스트 파일을 디코딩할 수 없습니다.")
                
    @staticmethod
    def extract_from_pdf(file_content: bytes) -> str:
        """PDF 파일에서 텍스트 추출"""
        try:
            # import fitz
            
            # # 메모리에서 직접 PDF 열기
            # doc = fitz.open(stream=file_content, filetype="pdf")
            # try:
            #     text = []
            #     for page in doc:
            #         text.append(page.get_text())
                    
            #     extracted_text = "".join(text).strip()
            #     if not extracted_text:
            #         logger.warning("PDF에서 텍스트를 추출했으나 내용이 비어있습니다. OCR 처리를 시도합니다.")
            #         # OCR 처리 시도
            #         return DocumentExtractor().extract_using_document_ai(file_content, "application/pdf")
            #     print(f"extracted_text: {extracted_text}")
            #     return extracted_text
            from langchain_community.document_loaders import PyMuPDFLoader
            try:
                # 임시 파일 생성하여 PDF 내용 저장
                with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_pdf:
                    temp_pdf.write(file_content)
                    temp_pdf_path = temp_pdf.name
                
                loader = PyMuPDFLoader(temp_pdf_path)
                pages = loader.load()
                
                print("=== PDF 내용 ===")
                print(f"총 페이지 수: {len(pages)}")
                cleaned_text_list = []
                for page in pages:
                    cleaned_text_list.append(page.page_content.strip())

                extracted_text = "\n".join(cleaned_text_list)
                
                # 텍스트가 비어있으면 OCR 처리 시도
                if not extracted_text:
                    logger.warning("PDF에서 텍스트를 추출했으나 내용이 비어있습니다. OCR 처리를 시도합니다.")
                    return DocumentExtractor().extract_using_document_ai(file_content, "application/pdf")
                    
                return extracted_text
            finally:
                # 임시 파일 삭제
                try:
                    if 'temp_pdf_path' in locals():
                        os.unlink(temp_pdf_path)
                except Exception as e:
                    logger.warning(f"임시 PDF 파일 삭제 실패: {str(e)}")
                    pass
        except ImportError as e:
            logger.error(f"PyMuPDF(fitz) 라이브러리가 설치되지 않았습니다: {str(e)}")
            raise RuntimeError(f"PDF 처리를 위한 라이브러리 오류: {str(e)}")
        except Exception as e:
            logger.error(f"PDF 텍스트 추출 중 오류 발생: {str(e)}")
            # 일반적인 텍스트 추출 실패 시 OCR 시도
            try:
                return DocumentExtractor().extract_using_document_ai(file_content, "application/pdf")
            except Exception as ocr_error:
                logger.error(f"OCR 처리 중 오류 발생: {str(ocr_error)}")
                raise RuntimeError(f"PDF 텍스트 추출 및 OCR 처리 실패: {str(e)}")
            
    @staticmethod
    def extract_from_docx(file_content: bytes) -> str:
        """DOCX 파일에서 텍스트 추출 (Tika 사용)"""
        try:
            # Tika 파서로 문서 처리
            parsed = parser.from_buffer(file_content, requestOptions={'timeout': 300})
            if not parsed:
                logger.warning("문서 파싱 실패")
                return None
                
            text = parsed.get('content', '')
            metadata = parsed.get('metadata', {})
            #print(f"metadata: {metadata}")
            if not text or not text.strip():
                logger.warning("문서에서 텍스트를 추출했으나 내용이 비어있습니다.")
                return None
                
            return text.strip()
        except Exception as e:
            logger.error(f"문서 텍스트 추출 중 오류 발생: {str(e)}")
            raise RuntimeError(f"문서 텍스트 추출 실패: {str(e)}")
            
    @staticmethod
    def extract_from_doc(file_content: bytes) -> str:
        """DOC 파일에서 텍스트 추출 (Tika 사용)"""
        try:
            # Tika 파서로 문서 처리
            parsed = parser.from_buffer(file_content, requestOptions={'timeout': 300})
            if not parsed:
                logger.warning("DOC 문서 파싱 실패")
                return None
                
            text = parsed.get('content', '')
            if not text or not text.strip():
                logger.warning("DOC 문서에서 텍스트를 추출했으나 내용이 비어있습니다.")
                return None
                
            return text.strip()
        except Exception as e:
            logger.error(f"DOC 텍스트 추출 중 오류 발생: {str(e)}")
            raise RuntimeError(f"DOC 텍스트 추출 실패: {str(e)}")
            
    @staticmethod
    def extract_from_excel(content: bytes) -> str:
        """엑셀 파일에서 텍스트를 추출합니다."""
        try:
            import pandas as pd
            from io import BytesIO
            
            # 모든 시트의 텍스트를 저장할 리스트
            all_text = []
            
            # 엑셀 파일의 모든 시트를 읽음
            excel_file = pd.ExcelFile(BytesIO(content))
            for sheet_name in excel_file.sheet_names:
                df = pd.read_excel(excel_file, sheet_name=sheet_name)
                sheet_text = f"\n[{sheet_name}]\n" + df.to_string(index=False).strip()
                all_text.append(sheet_text)
            
            # 모든 시트의 텍스트를 결합
            return "\n\n".join(all_text).strip()
        except Exception as e:
            logger.error(f"엑셀 텍스트 추출 중 오류 발생: {str(e)}")
            raise RuntimeError(f"엑셀 텍스트 추출 실패: {str(e)}")
            
    def extract_from_image(self, content: bytes) -> str:
        """이미지 파일에서 텍스트를 추출합니다."""
        try:
            return self.extract_using_vision_api(content)
        except Exception as e:
            logger.error(f"이미지 텍스트 추출 중 오류 발생: {str(e)}")
            raise RuntimeError(f"이미지 텍스트 추출 실패: {str(e)}")

    def extract_using_vision_api(self, content: bytes) -> str:
        """Google Cloud Vision API를 사용하여 이미지에서 텍스트를 추출합니다."""
        try:
            self._init_vision_ai()  # Vision 클라이언트 초기화
            from google.cloud import vision  # vision 모듈 임포트
            
            image = vision.Image(content=content)
            response = self.vision_client.text_detection(image=image)
            texts = response.text_annotations
            
            if not texts:
                logger.warning("Vision API: 텍스트가 감지되지 않음")
                return None
                
            # 첫 번째 항목이 전체 텍스트를 포함
            return texts[0].description.strip()
        except Exception as e:
            logger.error(f"Vision API 텍스트 추출 실패: {str(e)}")
            raise RuntimeError(f"Vision API 텍스트 추출 실패: {str(e)}")
            
    def extract_using_document_ai(self, file_content: bytes, mime_type: str) -> str:
        """Google Cloud Document AI를 사용한 텍스트 추출"""
        try:
            self._init_document_ai()
            raw_document = documentai.RawDocument(
                content=file_content,
                mime_type=mime_type
            )
            request = documentai.ProcessRequest(
                name=self.processor_name,
                raw_document=raw_document
            )
            
            response = self.document_client.process_document(request=request)
            document = response.document
            
            return document.text.strip()
        except Exception as e:
            logger.error(f"Document AI 텍스트 추출 실패: {str(e)}")
            raise RuntimeError(f"Document AI 텍스트 추출 실패: {str(e)}")
            
    @staticmethod
    def extract_from_tika(content: bytes) -> str:
        """Tika를 사용하여 파일에서 텍스트를 추출합니다."""
        from tika import parser
        
        try:
            parsed = parser.from_buffer(content)
            if not parsed:
                logger.warning("Tika 파싱 실패")
                return None
            
            text = parsed.get('content', '')
            if not text or not text.strip():
                logger.warning("Tika로 추출했으나 텍스트가 비어있음")
                return None
            
            return text.strip()
        except Exception as e:
            logger.error(f"Tika 텍스트 추출 중 오류 발생: {str(e)}")
            raise RuntimeError(f"Tika 텍스트 추출 실패: {str(e)}")

    def extract_from_hwp(self, content: bytes) -> str:
        """HWP 파일에서 텍스트를 추출합니다."""
        try:
            return self.extract_from_tika(content)
        except Exception as e:
            logger.error(f"HWP 텍스트 추출 중 오류 발생: {str(e)}")
            raise RuntimeError(f"HWP 텍스트 추출 실패: {str(e)}")
