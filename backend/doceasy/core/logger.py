import logging
import sys

# 로거 생성
logger = logging.getLogger(__name__)

# 로그 레벨 설정
logger.setLevel(logging.INFO)
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)


# 콘솔 핸들러 추가
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

# 포맷터 설정
#formatter = ColorFormatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)

# 핸들러 추가
logger.addHandler(console_handler)
