import gc
import time
import psutil
import os

def perform_garbage_collection():
    """
    가비지 컬렉션을 수행하고 메모리 사용량을 보고합니다.
    """
    # 현재 프로세스 가져오기
    process = psutil.Process(os.getpid())
    
    # 가비지 컬렉션 전 메모리 사용량
    mem_before = process.memory_info().rss / 1024 / 1024  # MB 단위로 변환
    
    # 수집 대상 객체 수 확인
    collected_before = gc.get_count()
    print(f"가비지 컬렉션 전 상태: {collected_before}")
    print(f"메모리 사용량 (수집 전): {mem_before:.2f} MB")
    
    # 가비지 컬렉션 수행 시간 측정 시작
    start_time = time.time()
    
    # 가비지 컬렉션 수행
    collected = gc.collect(generation=2)  # 모든 세대(0, 1, 2) 중 가장 오래된 객체 포함
    
    # 수행 시간 계산
    elapsed_time = time.time() - start_time
    
    # 가비지 컬렉션 후 메모리 사용량
    mem_after = process.memory_info().rss / 1024 / 1024  # MB 단위로 변환
    
    # 결과 출력
    print(f"가비지 컬렉션 완료: {collected}개 객체 수집됨")
    print(f"수행 시간: {elapsed_time:.4f}초")
    print(f"메모리 사용량 (수집 후): {mem_after:.2f} MB")
    print(f"절약된 메모리: {mem_before - mem_after:.2f} MB")
    
    # 비활성화된 객체 목록 (디버깅용)
    # unreachable = gc.get_objects()
    # print(f"도달할 수 없는 객체 수: {len(unreachable)}")
    
    return collected

if __name__ == "__main__":
    # 테스트용 메모리 낭비 객체 생성
    print("메모리에 큰 리스트 생성 중...")
    large_list = [i for i in range(1000000)]
    
    # 순환 참조 생성 (가비지 컬렉터가 처리해야 할 대상)
    class CircularReference:
        def __init__(self):
            self.ref = None
    
    obj1 = CircularReference()
    obj2 = CircularReference()
    obj1.ref = obj2
    obj2.ref = obj1
    
    # 참조 제거
    large_list = None
    obj1 = None
    obj2 = None
    
    # 가비지 컬렉션 수행
    print("\n가비지 컬렉션 수행...")
    perform_garbage_collection()
