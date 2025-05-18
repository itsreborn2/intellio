import asyncio
import psycopg2
from psycopg2.extras import execute_values
from sqlalchemy import text

from common.services.embedding import EmbeddingService
from common.services.embedding_models import EmbeddingModelType
from common.core.config import settings
from common.core.database import DATABASE_URL_SYNC  # 여기서 직접 동기식 연결 URL을 임포트
from loguru import logger
from common.core.database import AsyncSessionLocal

# CREATE TABLE IF NOT EXISTS stockeasy.web_search_cache
# (
#     id integer NOT NULL DEFAULT nextval('stockeasy.web_search_cache_id_seq'::regclass),
#     query text COLLATE pg_catalog."default",
#     "timestamp" timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
#     embedding vector(3072),
#     CONSTRAINT web_search_cache_pkey PRIMARY KEY (id)
# )
# docker compose exec postgres psql -U ${POSTGRES_USER} -d ${POSTGRES_DB} -c "CREATE EXTENSION IF NOT EXISTS vector;"

async def main():
    # 검색할 쿼리 입력
    search_query = "콜마홀딩스 경영권 분쟁"
    
    # 쿼리 임베딩 생성
    em_service = EmbeddingService()
    em_service.change_model(EmbeddingModelType.OPENAI_3_LARGE)
    
    logger.info(f"검색 쿼리: {search_query}")
    embedding_result = await em_service.create_embeddings_batch([search_query])
    query_embedding = embedding_result[0]
    
    # 임베딩 차원 확인
    logger.info(f"쿼리 임베딩 차원: {len(query_embedding)}")
    
    # PostgreSQL에서 유사도 검색
    results = await search_similar_embeddings(query_embedding)
    
    # 결과 출력
    logger.info("=== 유사도 검색 결과 ===")
    for idx, (id, query, distance) in enumerate(results, 1):
        logger.info(f"{idx}. ID: {id}, 거리: {distance:.4f}, 쿼리: {query}")

async def search_similar_embeddings(query_embedding, limit=5):
    """PostgreSQL에서 유사도 검색을 수행하는 함수"""
    # 쿼리 임베딩을 PostgreSQL 벡터 형식으로 변환
    embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"
    
    # 비동기 세션 생성
    async with AsyncSessionLocal() as session:
        try:
            # 1. 코사인 거리 유사도 검색 (<=>)
            sql = text("""
                SELECT id, query, embedding <=> :embedding AS distance
                FROM stockeasy.web_search_cache
                ORDER BY distance
                LIMIT :limit
            """)
            
            # 2. 유클리드 거리 유사도 검색 (<->)
            # sql = text("""
            #     SELECT id, query, embedding <-> :embedding AS distance
            #     FROM stockeasy.web_search_cache
            #     ORDER BY distance
            #     LIMIT :limit
            # """)
            
            # 3. 내적 유사도 검색 (<#>), 내적은 값이 클수록 유사하므로 내림차순 정렬
            # sql = text("""
            #     SELECT id, query, embedding <#> :embedding AS similarity
            #     FROM stockeasy.web_search_cache
            #     ORDER BY similarity DESC
            #     LIMIT :limit
            # """)
            
            result = await session.execute(
                sql, 
                {"embedding": embedding_str, "limit": limit}
            )
            
            # 결과 반환
            return result.all()
            
        except Exception as e:
            logger.error(f"유사도 검색 중 오류 발생: {str(e)}")
            raise

async def save_embeddings_to_postgres(queries, embeddings):
    """임베딩을 PostgreSQL에 저장하는 함수"""
    # 데이터베이스 모듈에서 정의된 동기식 URL 사용
    db_url = DATABASE_URL_SYNC
    
    # 차원 확인
    embedding_dimension = len(embeddings[0])
    logger.info(f"임베딩 차원: {embedding_dimension}")
    
    # SQLAlchemy URL을 psycopg2 연결 파라미터로 변환
    db_params = convert_sqlalchemy_url_to_params(db_url)
    logger.info(f"DB 연결: {db_params['host']}:{db_params['port']}/{db_params['database']}")
    
    # 연결 및 데이터 삽입
    try:
        with psycopg2.connect(**db_params) as conn:
            with conn.cursor() as cur:
                # 각 쿼리와 해당 임베딩을 테이블에 삽입
                for i, (query, embedding) in enumerate(zip(queries, embeddings)):
                    # PostgreSQL 배열 형식으로 변환
                    embedding_str = "{" + ",".join(str(x) for x in embedding) + "}"
                    
                    # 데이터 삽입
                    cur.execute(
                        "INSERT INTO stockeasy.web_search_cache (query, embedding) VALUES (%s, %s) RETURNING id",
                        (query, embedding_str)
                    )
                    
                    # 삽입된 ID 확인
                    inserted_id = cur.fetchone()[0]
                    logger.info(f"삽입 완료: ID={inserted_id}, 쿼리='{query[:30]}...'")
                
                conn.commit()
                logger.info(f"총 {len(queries)}개 임베딩을 PostgreSQL에 저장했습니다.")
    except Exception as e:
        logger.error(f"PostgreSQL 저장 중 오류 발생: {str(e)}")
        raise

def convert_sqlalchemy_url_to_params(url):
    """SQLAlchemy URL을 psycopg2 파라미터로 변환"""
    # postgresql+psycopg2://username:password@host:port/database
    url = url.replace('postgresql+psycopg2://', '')
    
    # 사용자 정보와 호스트 정보 분리
    auth, rest = url.split('@', 1)
    
    # 사용자 이름과 비밀번호 분리
    if ':' in auth:
        username, password = auth.split(':', 1)
    else:
        username, password = auth, None
    
    # 호스트, 포트, 데이터베이스 분리
    if '/' in rest:
        host_port, database = rest.split('/', 1)
    else:
        host_port, database = rest, ''
    
    # 호스트와 포트 분리
    if ':' in host_port:
        host, port = host_port.split(':', 1)
        port = int(port)
    else:
        host, port = host_port, 5432
    
    return {
        'host': host,
        'port': port,
        'user': username,
        'password': password,
        'database': database
    }

if __name__ == "__main__":
    asyncio.run(main())