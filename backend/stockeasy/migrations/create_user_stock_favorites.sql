-- 관심기업(즐겨찾기) 테이블 생성 및 마이그레이션
-- PM 지시사항에 따른 새로운 구조 적용

-- 1. 새로운 user_stock_favorites 테이블 생성
CREATE TABLE IF NOT EXISTS stockeasy.user_stock_favorites (
    id SERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    stock_code VARCHAR(10) NOT NULL,
    stock_name VARCHAR(100),
    category VARCHAR(50) NOT NULL DEFAULT 'default',
    display_order INTEGER NOT NULL DEFAULT 0,
    memo TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- 2. 인덱스 생성 (PM 지시사항에 따른 성능 최적화)
-- 필수 인덱스 (성능 핵심)
CREATE INDEX IF NOT EXISTS idx_user_category_display 
ON stockeasy.user_stock_favorites (user_id, category, display_order);

CREATE UNIQUE INDEX IF NOT EXISTS idx_user_stock_category_unique 
ON stockeasy.user_stock_favorites (user_id, stock_code, category);

-- 분석용 인덱스
CREATE INDEX IF NOT EXISTS idx_stock_code_name ON stockeasy.user_stock_favorites (stock_code, stock_name);

-- 3. 기존 데이터 마이그레이션 (user_rs_favorites -> user_stock_favorites)
INSERT INTO stockeasy.user_stock_favorites (user_id, stock_code, stock_name, category, display_order, created_at, updated_at)
SELECT 
    user_id,
    stock_code,
    stock_name,
    'default' as category,
    ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY created_at) as display_order,
    created_at,
    updated_at
FROM stockeasy.user_rs_favorites
ON CONFLICT (user_id, stock_code, category) DO NOTHING;

-- 4. 기존 테이블 백업 후 삭제 (선택사항 - 주석 처리)
-- CREATE TABLE IF NOT EXISTS stockeasy.user_rs_favorites_backup AS SELECT * FROM stockeasy.user_rs_favorites;
-- DROP TABLE IF EXISTS stockeasy.user_rs_favorites;

COMMENT ON TABLE stockeasy.user_stock_favorites IS 'User stock favorites table with category management';
COMMENT ON COLUMN stockeasy.user_stock_favorites.category IS 'User defined category name (default: default)';
COMMENT ON COLUMN stockeasy.user_stock_favorites.display_order IS 'Display order within category';
COMMENT ON COLUMN stockeasy.user_stock_favorites.memo IS 'User memo';
