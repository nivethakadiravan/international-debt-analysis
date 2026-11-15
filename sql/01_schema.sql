-- =====================================================================
-- International Debt Analysis - Database Schema
-- Target: MySQL 8.0+ (window functions + CTEs). Also runs on MariaDB 10.5+.
-- =====================================================================

DROP DATABASE IF EXISTS international_debt_db;
CREATE DATABASE international_debt_db
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE international_debt_db;

-- ---------------------------------------------------------------------
-- 1. countries : one row per country (plus World Bank regional /
--    income-group aggregates, flagged with is_aggregate = 1 so they are
--    never double-counted with the countries they contain)
-- ---------------------------------------------------------------------
CREATE TABLE countries (
    country_id        INT          NOT NULL PRIMARY KEY,
    country_code      CHAR(3)      NOT NULL,
    country_name      VARCHAR(120) NOT NULL,
    region            VARCHAR(60)  NULL,
    income_group      VARCHAR(40)  NULL,
    lending_category  VARCHAR(20)  NULL,
    is_aggregate      TINYINT(1)   NOT NULL DEFAULT 0,
    CONSTRAINT uq_country_code UNIQUE (country_code)
) ENGINE = InnoDB;

CREATE INDEX idx_countries_region ON countries (region);
CREATE INDEX idx_countries_income ON countries (income_group);

-- ---------------------------------------------------------------------
-- 2. indicators : one row per World Bank debt series
--    unit     : USD / Percent / Years / Other
--    category : Debt outstanding (stock), Interest payments, ...
-- ---------------------------------------------------------------------
CREATE TABLE indicators (
    indicator_id      INT           NOT NULL PRIMARY KEY,
    indicator_code    VARCHAR(40)   NOT NULL,
    indicator_name    VARCHAR(255)  NOT NULL,
    topic             VARCHAR(150)  NULL,
    short_definition  VARCHAR(1000) NULL,
    unit              VARCHAR(10)   NOT NULL,
    category          VARCHAR(40)   NOT NULL,
    CONSTRAINT uq_indicator_code UNIQUE (indicator_code)
) ENGINE = InnoDB;

CREATE INDEX idx_indicators_category ON indicators (category, unit);

-- ---------------------------------------------------------------------
-- 3. debt_data : fact table, one value per country x indicator x year
--    (the raw file's 33 year-columns reshaped into rows)
-- ---------------------------------------------------------------------
CREATE TABLE debt_data (
    debt_id        BIGINT        NOT NULL AUTO_INCREMENT PRIMARY KEY,
    country_id     INT           NOT NULL,
    indicator_id   INT           NOT NULL,
    year           SMALLINT      NOT NULL,
    value          DECIMAL(22,4) NOT NULL,
    is_projection  TINYINT(1)    NOT NULL DEFAULT 0,   -- 1 = year after 2024 (projected)

    CONSTRAINT fk_debt_country   FOREIGN KEY (country_id)   REFERENCES countries (country_id),
    CONSTRAINT fk_debt_indicator FOREIGN KEY (indicator_id) REFERENCES indicators (indicator_id),
    CONSTRAINT uq_debt_point     UNIQUE (country_id, indicator_id, year),
    CONSTRAINT chk_year          CHECK (year BETWEEN 1970 AND 2050)
) ENGINE = InnoDB;

-- Most queries filter by indicator + year, then group by country
CREATE INDEX idx_debt_indicator_year ON debt_data (indicator_id, year);
CREATE INDEX idx_debt_year           ON debt_data (year);
