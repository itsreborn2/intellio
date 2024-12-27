from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
import os

def create_test_image(text, output_path, format='JPEG'):
    """테스트용 이미지 생성"""
    # 흰색 배경의 이미지 생성
    width = 800
    height = 400
    image = Image.new('RGB', (width, height), 'white')
    draw = ImageDraw.Draw(image)
    
    # 기본 폰트 사용 (실제 환경에서는 한글 폰트 경로 지정 필요)
    try:
        font = ImageFont.truetype("malgun.ttf", 40)  # Windows 기본 한글 폰트
    except:
        font = ImageFont.load_default()
    
    # 텍스트 그리기
    text_bbox = draw.textbbox((0, 0), text, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]
    
    x = (width - text_width) // 2
    y = (height - text_height) // 2
    
    draw.text((x, y), text, fill='black', font=font)
    
    # 이미지 저장
    image.save(output_path, format)

def main():
    # 테스트 파일 디렉토리
    test_files_dir = Path(__file__).parent / 'test_files'
    test_files_dir.mkdir(exist_ok=True)
    
    # 테스트 텍스트
    test_text = "인텔리오 테스트\nIntellIO Test\n2024년"
    
    # 여러 포맷으로 저장
    formats = [
        ('JPEG', 'jpg'),
        ('PNG', 'png'),
        ('TIFF', 'tiff')
    ]
    
    for format_name, extension in formats:
        output_path = test_files_dir / f'test_document.{extension}'
        create_test_image(test_text, output_path, format_name)
        print(f"Created {format_name} image: {output_path}")

if __name__ == '__main__':
    main()
