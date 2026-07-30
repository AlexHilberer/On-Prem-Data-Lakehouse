#!/usr/bin/env bash
set -euo pipefail

create_database() {
  local database="$1"
  local username="$2"
  local password="$3"
  psql --set ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<SQL
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '${username}') THEN
    CREATE ROLE ${username} LOGIN PASSWORD '${password}';
  END IF;
END
\$\$;
SELECT 'CREATE DATABASE ${database} OWNER ${username}'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '${database}')\gexec
SQL
}

create_database airflow airflow "$AIRFLOW_DB_PASSWORD"
create_database ranger ranger "$RANGER_DB_PASSWORD"
create_database polaris polaris "$POLARIS_DB_PASSWORD"
create_database superset superset "$SUPERSET_DB_PASSWORD"
create_database retail source_app "$SOURCE_DB_PASSWORD"

psql --set ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname retail <<'SQL'
SET ROLE source_app;
CREATE SCHEMA IF NOT EXISTS source AUTHORIZATION source_app;
CREATE TABLE IF NOT EXISTS source.ingestion_batches (
  batch_id uuid PRIMARY KEY,
  generated_at timestamptz NOT NULL DEFAULT now(),
  seed bigint NOT NULL,
  requested_rows integer NOT NULL CHECK (requested_rows > 0),
  period_start date,
  period_end date,
  actual_rows integer
);
CREATE TABLE IF NOT EXISTS source.customers (
  customer_id bigint PRIMARY KEY,
  batch_id uuid NOT NULL REFERENCES source.ingestion_batches(batch_id),
  full_name text NOT NULL,
  email text NOT NULL,
  country text NOT NULL,
  customer_segment text NOT NULL,
  created_at timestamptz NOT NULL,
  city text,
  region text,
  acquisition_channel text
);
CREATE INDEX IF NOT EXISTS customers_batch_idx ON source.customers(batch_id);
CREATE TABLE IF NOT EXISTS source.orders (
  order_id bigint PRIMARY KEY,
  batch_id uuid NOT NULL REFERENCES source.ingestion_batches(batch_id),
  customer_id bigint NOT NULL REFERENCES source.customers(customer_id),
  ordered_at timestamptz NOT NULL,
  status text NOT NULL,
  currency text NOT NULL,
  sales_channel text,
  payment_method text,
  campaign_id bigint,
  shipped_at timestamptz,
  delivered_at timestamptz
);
CREATE INDEX IF NOT EXISTS orders_batch_idx ON source.orders(batch_id);
CREATE TABLE IF NOT EXISTS source.order_items (
  order_item_id bigint PRIMARY KEY,
  batch_id uuid NOT NULL REFERENCES source.ingestion_batches(batch_id),
  order_id bigint NOT NULL REFERENCES source.orders(order_id),
  sku text NOT NULL,
  quantity integer NOT NULL CHECK (quantity > 0),
  unit_price numeric(12,2) NOT NULL CHECK (unit_price >= 0),
  product_id bigint,
  unit_cost numeric(12,2),
  discount_pct numeric(5,4) DEFAULT 0
);
CREATE INDEX IF NOT EXISTS order_items_batch_idx ON source.order_items(batch_id);
CREATE TABLE IF NOT EXISTS source.products (
  product_id bigint PRIMARY KEY,
  sku text UNIQUE NOT NULL,
  product_name text NOT NULL,
  category text NOT NULL,
  subcategory text NOT NULL,
  brand text NOT NULL,
  unit_cost numeric(12,2) NOT NULL,
  list_price numeric(12,2) NOT NULL
);
CREATE TABLE IF NOT EXISTS source.campaigns (
  campaign_id bigint PRIMARY KEY,
  campaign_name text UNIQUE NOT NULL,
  campaign_channel text NOT NULL,
  discount_rate numeric(5,4) NOT NULL
);
RESET ROLE;
SQL
