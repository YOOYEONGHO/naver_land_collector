-- 1. 새로운 테이블 생성 (3개 단지)
-- 기존 listings 테이블과 동일한 스키마로 생성합니다.

-- 1.1 DMC파크뷰자이 (108064)
create table if not exists listings_108064 (
  "articleNo" text not null,
  "atclNm" text,
  "rletTpNm" text,
  "tradTpNm" text,
  "price" text,
  "price_int" bigint,
  "spc1" text,
  "spc2" text,
  "floorInfo" text,
  "direction" text,
  "lat" float,
  "lng" float,
  "tradePrice" text,
  "realtorName" text,
  "buildingName" text,
  "timestamp" text,
  "atclFetrDesc" text,
  "cfmYmd" text,
  created_at timestamptz default now()
);

-- 1.2 마포래미안푸르지오 (104917)
create table if not exists listings_104917 (
  "articleNo" text not null,
  "atclNm" text,
  "rletTpNm" text,
  "tradTpNm" text,
  "price" text,
  "price_int" bigint,
  "spc1" text,
  "spc2" text,
  "floorInfo" text,
  "direction" text,
  "lat" float,
  "lng" float,
  "tradePrice" text,
  "realtorName" text,
  "buildingName" text,
  "timestamp" text,
  "atclFetrDesc" text,
  "cfmYmd" text,
  created_at timestamptz default now()
);

-- 1.3 남산타운 (3833)
create table if not exists listings_3833 (
  "articleNo" text not null,
  "atclNm" text,
  "rletTpNm" text,
  "tradTpNm" text,
  "price" text,
  "price_int" bigint,
  "spc1" text,
  "spc2" text,
  "floorInfo" text,
  "direction" text,
  "lat" float,
  "lng" float,
  "tradePrice" text,
  "realtorName" text,
  "buildingName" text,
  "timestamp" text,
  "atclFetrDesc" text,
  "cfmYmd" text,
  created_at timestamptz default now()
);

-- 2. 인덱스 생성 (성능 최적화)
-- timestamp: 최신순 정렬 및 시계열 조회 시 필수
-- articleNo: 특정 매물의 이력 조회 시 사용

-- 2.1 DMC파크뷰자이 인덱스
CREATE INDEX idx_listings_108064_timestamp ON listings_108064 ("timestamp" DESC);
CREATE INDEX idx_listings_108064_articleNo ON listings_108064 ("articleNo");

-- 2.2 마포래미안푸르지오 인덱스
CREATE INDEX idx_listings_104917_timestamp ON listings_104917 ("timestamp" DESC);
CREATE INDEX idx_listings_104917_articleNo ON listings_104917 ("articleNo");

-- 2.3 남산타운 인덱스
CREATE INDEX idx_listings_3833_timestamp ON listings_3833 ("timestamp" DESC);
CREATE INDEX idx_listings_3833_articleNo ON listings_3833 ("articleNo");


-- 3. 데이터 이관 (마이그레이션)
-- 기존 queries remain same...
insert into listings_108064 
select * from listings;
