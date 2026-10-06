-- UK Food Price Tracker: SQL layer (MySQL 8 syntax; also runs on SQLite with LN/EXP available)
-- Loads ONS CPI price quotes for January 2021 and January 2025 and compares
-- the SAME item in the SAME shop in both years (matched pairs).

-- ------------------------------------------------------------------ 1. Schema
CREATE TABLE price_quotes (
    quote_date   INT,            -- YYYYMM
    item_id      INT,
    item_desc    VARCHAR(60),
    validity     INT,            -- 3/4 = valid quote; 1 = no price collected
    shop_code    INT,
    price        DECIMAL(10,2),
    region       INT,            -- 1 = head-office catalogue, 2 = London ... 13 = Northern Ireland
    shop_type    INT             -- 1 = multiple (10+ outlets), 2 = independent
);

CREATE TABLE region_names (region INT PRIMARY KEY, region_name VARCHAR(30));
INSERT INTO region_names VALUES
 (2,'London'),(3,'South East'),(4,'South West'),(5,'East Anglia'),(6,'East Midlands'),
 (7,'West Midlands'),(8,'Yorkshire & Humber'),(9,'North West'),(10,'North'),
 (11,'Wales'),(12,'Scotland'),(13,'Northern Ireland');

-- ------------------------------------------------------------------ 2. Clean view: valid food quotes
CREATE VIEW v_food_quotes AS
SELECT quote_date, item_id, item_desc, shop_code, region, shop_type, price
FROM price_quotes
WHERE item_id BETWEEN 210000 AND 219999      -- food items
  AND validity IN (3, 4)                     -- valid quotes only
  AND price > 0;

-- ------------------------------------------------------------------ 3. Matched pairs (same item, shop, region)
CREATE VIEW v_matched_pairs AS
SELECT a.item_id, a.region, a.shop_code, a.shop_type,
       a.price AS price_2021, b.price AS price_2025,
       b.price / a.price AS price_relative
FROM (SELECT item_id, region, shop_code, MIN(shop_type) AS shop_type, AVG(price) AS price
      FROM v_food_quotes WHERE quote_date = 202101
      GROUP BY item_id, region, shop_code) a
JOIN (SELECT item_id, region, shop_code, AVG(price) AS price
      FROM v_food_quotes WHERE quote_date = 202501
      GROUP BY item_id, region, shop_code) b
  ON a.item_id = b.item_id AND a.region = b.region AND a.shop_code = b.shop_code
WHERE b.price / a.price > 0.2 AND b.price / a.price < 5;  -- drop implausible matches (product or unit changed)

-- ------------------------------------------------------------------ 4. Price change per item (geometric mean of relatives)
SELECT p.item_id,
       MAX(q.item_desc)                                AS item,
       COUNT(*)                                        AS matched_shops,
       ROUND((EXP(AVG(LN(p.price_relative))) - 1) * 100, 1) AS pct_change_2021_2025
FROM v_matched_pairs p
JOIN (SELECT item_id, MAX(item_desc) AS item_desc FROM v_food_quotes WHERE quote_date = 202501 GROUP BY item_id) q
  ON q.item_id = p.item_id
GROUP BY p.item_id
HAVING COUNT(*) >= 20
ORDER BY pct_change_2021_2025 DESC;

-- ------------------------------------------------------------------ 5. Regional change on a like-for-like basket
WITH item_region AS (
    SELECT region, item_id, COUNT(*) AS n, AVG(LN(price_relative)) AS log_rel
    FROM v_matched_pairs
    WHERE region BETWEEN 2 AND 13
    GROUP BY region, item_id
    HAVING COUNT(*) >= 3
),
basket AS (                                  -- items priced in all 12 regions
    SELECT item_id FROM item_region GROUP BY item_id HAVING COUNT(DISTINCT region) = 12
)
SELECT r.region_name,
       ROUND((EXP(AVG(ir.log_rel)) - 1) * 100, 1) AS pct_change_2021_2025
FROM item_region ir
JOIN basket b ON b.item_id = ir.item_id
JOIN region_names r ON r.region = ir.region
GROUP BY r.region_name
ORDER BY pct_change_2021_2025 DESC;
