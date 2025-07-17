"""메모리 모니터링 유틸리티"""

import asyncio
import gc
import os
import psutil
import objgraph
from datetime import datetime
from pathlib import Path
import csv
from typing import Dict, List, Any
from loguru import logger
import weakref


class MemoryMonitor:
    """메모리 사용량 모니터링 클래스"""
    
    def __init__(self):
        self.baseline = None
        self.samples = []
        self.tracked_objects = {}
        self.weak_refs = {}
        
    def track_object(self, obj: Any, name: str):
        """특정 객체의 참조 추적"""
        try:
            self.weak_refs[name] = weakref.ref(obj)
            logger.info(f"[메모리추적] {name} 객체 추적 시작")
        except TypeError:
            logger.warning(f"[메모리추적] {name} 객체는 weakref 불가능")
            
    def check_leaked_refs(self) -> Dict[str, int]:
        """여전히 살아있는 추적 객체 확인"""
        alive = {}
        for name, ref in self.weak_refs.items():
            if ref() is not None:
                import sys
                alive[name] = sys.getrefcount(ref())
        return alive
        
    async def monitor_memory(self, interval: int = 60):
        """주기적으로 메모리 상태 모니터링"""
        process = psutil.Process(os.getpid())
        
        # CSV 파일 설정
        csv_path = Path("backend/stockeasy/local_cache/memory_tracking/memory_monitor.csv")
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        
        # CSV 헤더
        if not csv_path.exists():
            with open(csv_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'timestamp', 'rss_mb', 'vms_mb', 
                    'dict_count', 'list_count', 'tuple_count',
                    'AgentState_count', 'ClientSession_count',
                    'DataFrame_count', 'gc_objects', 'gc_garbage'
                ])
        
        while True:
            try:
                # 메모리 정보
                mem_info = process.memory_info()
                rss_mb = mem_info.rss / (1024 * 1024)
                vms_mb = mem_info.vms / (1024 * 1024)
                
                # 객체 수 카운트
                counts = {
                    'dict': objgraph.count('dict'),
                    'list': objgraph.count('list'),
                    'tuple': objgraph.count('tuple'),
                    'AgentState': objgraph.count('AgentState'),
                    'ClientSession': objgraph.count('ClientSession'),
                    'DataFrame': objgraph.count('DataFrame')
                }
                
                # 가비지 컬렉션 정보
                gc_stats = {
                    'objects': len(gc.get_objects()),
                    'garbage': len(gc.garbage)
                }
                
                # 증가하는 객체 찾기
                if self.baseline:
                    growth = objgraph.growth(limit=10)
                    if growth:
                        logger.warning(f"[메모리모니터] 객체 증가 감지:")
                        for name, count, delta in growth:
                            logger.warning(f"  {name}: {count} (+{delta})")
                else:
                    self.baseline = objgraph.typestats()
                
                # CSV에 기록
                with open(csv_path, 'a', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        datetime.now().isoformat(),
                        round(rss_mb, 2),
                        round(vms_mb, 2),
                        counts['dict'],
                        counts['list'],
                        counts['tuple'],
                        counts['AgentState'],
                        counts['ClientSession'],
                        counts['DataFrame'],
                        gc_stats['objects'],
                        gc_stats['garbage']
                    ])
                
                # 로그 출력
                logger.info(f"[메모리모니터] RSS: {rss_mb:.1f}MB, VMS: {vms_mb:.1f}MB")
                logger.info(f"[메모리모니터] 객체 수 - dict: {counts['dict']}, list: {counts['list']}, AgentState: {counts['AgentState']}")
                
                # 누수된 참조 확인
                leaked = self.check_leaked_refs()
                if leaked:
                    logger.warning(f"[메모리모니터] 여전히 살아있는 추적 객체: {leaked}")
                
                # 순환 참조 검사
                gc.collect()
                if gc.garbage:
                    logger.error(f"[메모리모니터] 가비지 컬렉션 불가 객체: {len(gc.garbage)}개")
                    # 상위 10개만 출력
                    for i, obj in enumerate(gc.garbage[:10]):
                        logger.error(f"  {i}: {type(obj).__name__}")
                
            except Exception as e:
                logger.error(f"[메모리모니터] 모니터링 중 오류: {str(e)}")
                
            await asyncio.sleep(interval)


async def find_memory_leaks():
    """메모리 누수 지점 찾기"""
    import tracemalloc
    
    # 메모리 추적 시작
    tracemalloc.start(25)
    
    # 10분 대기 후 스냅샷
    await asyncio.sleep(600)
    
    snapshot = tracemalloc.take_snapshot()
    top_stats = snapshot.statistics('lineno')
    
    logger.warning("[메모리누수] 상위 30개 메모리 사용 위치:")
    for stat in top_stats[:30]:
        size_mb = stat.size / (1024 * 1024)
        if size_mb > 1:  # 1MB 이상만
            logger.warning(f"{stat.filename}:{stat.lineno}: {size_mb:.1f} MB")
            
            # 추가 정보 얻기
            for line in stat.traceback.format():
                logger.warning(f"  {line}")


if __name__ == "__main__":
    # 메모리 모니터 실행
    monitor = MemoryMonitor()
    
    # 비동기 태스크 실행
    async def main():
        # 두 태스크를 동시에 실행
        await asyncio.gather(
            monitor.monitor_memory(interval=30),  # 30초마다
            find_memory_leaks()  # 10분 후 누수 지점 찾기
        )
    
    asyncio.run(main()) 