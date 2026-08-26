#!/usr/bin/env python3
import argparse
import os
import random
import uuid
from datetime import date, datetime, time, timedelta, timezone

import psycopg2
from faker import Faker
from psycopg2.extras import execute_values


COUNTRIES = {
    "DE": (("Berlin", "East"), ("Munich", "South"), ("Hamburg", "North")),
    "FR": (("Paris", "Île-de-France"), ("Lyon", "Auvergne-Rhône-Alpes")),
    "NL": (("Amsterdam", "North Holland"), ("Rotterdam", "South Holland")),
    "PL": (("Warsaw", "Masovia"), ("Kraków", "Lesser Poland")),
    "ES": (("Madrid", "Community of Madrid"), ("Barcelona", "Catalonia")),
    "IT": (("Milan", "Lombardy"), ("Rome", "Lazio")),
}
SEGMENTS = ("consumer", "small_business", "enterprise")
CHANNELS = ("web", "mobile", "marketplace", "partner")
ACQUISITION_CHANNELS = ("organic", "paid_search", "social", "referral", "partner")
PAYMENT_METHODS = ("card", "paypal", "bank_transfer", "invoice")
PRODUCT_BLUEPRINTS = (
    ("Electronics", "Audio", ("Auralis", "VoltEdge"), ("Wireless Headphones", "Bluetooth Speaker", "Studio Earbuds"), 35, 240),
    ("Electronics", "Computing", ("Nexa", "VoltEdge"), ("Mechanical Keyboard", "Ergonomic Mouse", "USB-C Dock"), 30, 290),
    ("Home", "Kitchen", ("CasaNova", "NordHaus"), ("Coffee Grinder", "Chef Knife", "Smart Kettle"), 18, 170),
    ("Home", "Living", ("CasaNova", "NordHaus"), ("Desk Lamp", "Wool Throw", "Storage Set"), 12, 130),
    ("Sports", "Fitness", ("PeakForm", "MotionLab"), ("Yoga Mat", "Kettlebell", "Resistance Set"), 10, 150),
    ("Sports", "Outdoor", ("PeakForm", "TrailNorth"), ("Daypack", "Thermal Bottle", "Trekking Poles"), 15, 190),
    ("Fashion", "Essentials", ("Atelier One", "Urban Loom"), ("Premium T-Shirt", "Everyday Hoodie", "Classic Chinos"), 9, 120),
    ("Beauty", "Personal Care", ("PureKind", "Lumera"), ("Skin Care Set", "Hair Dryer", "Electric Shaver"), 14, 180),
)
CAMPAIGNS = (
    (1, "Always On", "all", 0.00),
    (2, "Spring Refresh", "social", 0.10),
    (3, "Summer Sale", "paid_search", 0.15),
    (4, "Black Friday", "web", 0.25),
    (5, "Partner Rewards", "partner", 0.08),
)


def ensure_schema(cursor) -> None:
    cursor.execute(
        """
        ALTER TABLE source.ingestion_batches
          ADD COLUMN IF NOT EXISTS period_start date,
          ADD COLUMN IF NOT EXISTS period_end date,
          ADD COLUMN IF NOT EXISTS actual_rows integer;
        ALTER TABLE source.customers
          ADD COLUMN IF NOT EXISTS city text,
          ADD COLUMN IF NOT EXISTS region text,
          ADD COLUMN IF NOT EXISTS acquisition_channel text;
        ALTER TABLE source.orders
          ADD COLUMN IF NOT EXISTS sales_channel text,
          ADD COLUMN IF NOT EXISTS payment_method text,
          ADD COLUMN IF NOT EXISTS campaign_id bigint,
          ADD COLUMN IF NOT EXISTS shipped_at timestamptz,
          ADD COLUMN IF NOT EXISTS delivered_at timestamptz;
        ALTER TABLE source.order_items
          ADD COLUMN IF NOT EXISTS product_id bigint,
          ADD COLUMN IF NOT EXISTS unit_cost numeric(12,2),
          ADD COLUMN IF NOT EXISTS discount_pct numeric(5,4) DEFAULT 0;
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
        """
    )


def product_catalog() -> list[tuple]:
    products = []
    product_id = 1
    for category, subcategory, brands, names, minimum, maximum in PRODUCT_BLUEPRINTS:
        for brand in brands:
            for name in names:
                list_price = round(minimum + ((product_id * 37) % (maximum - minimum)), 2)
                unit_cost = round(list_price * (0.42 + (product_id % 7) * 0.035), 2)
                products.append(
                    (
                        product_id,
                        f"SKU-{product_id:04d}",
                        f"{brand} {name}",
                        category,
                        subcategory,
                        brand,
                        unit_cost,
                        list_price,
                    )
                )
                product_id += 1
    return products


def resolve_period(cursor) -> tuple[date, date, bool]:
    cursor.execute(
        "SELECT max(period_end) FROM source.ingestion_batches WHERE period_end IS NOT NULL"
    )
    last_period_end = cursor.fetchone()[0]
    if last_period_end is None:
        period_end = datetime.now(timezone.utc).date()
        return period_end - timedelta(days=729), period_end, True
    period_start = last_period_end + timedelta(days=1)
    return period_start, period_start + timedelta(days=29), False


def weighted_choice(rng: random.Random, values, weights):
    return rng.choices(values, weights=weights, k=1)[0]


def generate_batch(
    database_url: str,
    rows: int | None,
    seed: int,
    batch_id: str | None = None,
) -> dict:
    resolved_batch_id = batch_id or str(uuid.uuid4())
    rng = random.Random(seed)
    faker = Faker()
    faker.seed_instance(seed)
    products = product_catalog()

    with psycopg2.connect(database_url) as connection:
        with connection.cursor() as cursor:
            ensure_schema(cursor)
            # Returning the recorded batch makes an Airflow retry idempotent.
            cursor.execute(
                "SELECT period_start, period_end, actual_rows FROM source.ingestion_batches WHERE batch_id = %s",
                (resolved_batch_id,),
            )
            existing_batch = cursor.fetchone()
            if existing_batch:
                return {
                    "batch_id": resolved_batch_id,
                    "period_start": existing_batch[0].isoformat(),
                    "period_end": existing_batch[1].isoformat(),
                    "rows": existing_batch[2],
                }

            # Automatic runs bootstrap two years, then advance in monthly windows.
            period_start, period_end, is_bootstrap = resolve_period(cursor)
            resolved_rows = rows if rows and rows > 0 else (25_000 if is_bootstrap else 3_000)
            execute_values(
                cursor,
                """
                INSERT INTO source.products
                  (product_id, sku, product_name, category, subcategory, brand, unit_cost, list_price)
                VALUES %s
                ON CONFLICT (product_id) DO UPDATE SET
                  sku = EXCLUDED.sku,
                  product_name = EXCLUDED.product_name,
                  category = EXCLUDED.category,
                  subcategory = EXCLUDED.subcategory,
                  brand = EXCLUDED.brand,
                  unit_cost = EXCLUDED.unit_cost,
                  list_price = EXCLUDED.list_price
                """,
                products,
            )
            execute_values(
                cursor,
                """
                INSERT INTO source.campaigns
                  (campaign_id, campaign_name, campaign_channel, discount_rate)
                VALUES %s
                ON CONFLICT (campaign_id) DO UPDATE SET
                  campaign_name = EXCLUDED.campaign_name,
                  campaign_channel = EXCLUDED.campaign_channel,
                  discount_rate = EXCLUDED.discount_rate
                """,
                CAMPAIGNS,
            )

            cursor.execute(
                """
                SELECT customer_id, customer_segment, country
                FROM source.customers
                ORDER BY customer_id
                """
            )
            existing_customers = cursor.fetchall()
            existing_customer_ids = [row[0] for row in existing_customers]
            new_customer_count = max(50, resolved_rows // (6 if is_bootstrap else 12))
            # Batch-derived IDs stay stable when the same batch is retried.
            id_base = uuid.UUID(resolved_batch_id).int % 1_000_000_000
            cursor.execute(
                """
                INSERT INTO source.ingestion_batches
                  (batch_id, seed, requested_rows, period_start, period_end, actual_rows)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    resolved_batch_id,
                    seed,
                    resolved_rows,
                    period_start,
                    period_end,
                    resolved_rows,
                ),
            )
            customers = []
            for offset in range(new_customer_count):
                customer_id = id_base * 10_000 + offset
                country = weighted_choice(
                    rng, tuple(COUNTRIES), (34, 18, 12, 13, 12, 11)
                )
                city, region = rng.choice(COUNTRIES[country])
                segment = weighted_choice(rng, SEGMENTS, (72, 20, 8))
                created_day = period_start - timedelta(days=rng.randint(0, 365))
                customers.append(
                    (
                        customer_id,
                        resolved_batch_id,
                        faker.name(),
                        faker.unique.email(),
                        country,
                        segment,
                        datetime.combine(created_day, time(), timezone.utc),
                        city,
                        region,
                        weighted_choice(
                            rng, ACQUISITION_CHANNELS, (32, 24, 19, 15, 10)
                        ),
                    )
                )
            execute_values(
                cursor,
                """
                INSERT INTO source.customers
                  (customer_id, batch_id, full_name, email, country, customer_segment,
                   created_at, city, region, acquisition_channel)
                VALUES %s
                """,
                customers,
            )
            orders = []
            items = []
            period_days = (period_end - period_start).days + 1
            category_weights = {
                "consumer": (34, 25, 18, 15, 8),
                "small_business": (48, 22, 15, 10, 5),
                "enterprise": (58, 18, 14, 7, 3),
            }
            customers_by_id = {
                row[0]: {"segment": row[5], "country": row[4]} for row in customers
            }
            for customer_id, segment, country in existing_customers:
                customers_by_id[customer_id] = {
                    "segment": segment,
                    "country": country,
                }

            products_by_category = {}
            for product in products:
                products_by_category.setdefault(product[3], []).append(product)
            categories = tuple(products_by_category)

            for offset in range(resolved_rows):
                order_id = id_base * 100_000 + offset
                if existing_customer_ids and rng.random() < 0.65:
                    customer_id = rng.choice(existing_customer_ids)
                else:
                    customer_id = rng.choice(customers)[0]
                customer = customers_by_id[customer_id]
                day_offset = rng.randrange(period_days)
                ordered_day = period_start + timedelta(days=day_offset)
                seasonal_factor = 1.08 if ordered_day.month in (11, 12) else 1.03 if ordered_day.month in (5, 6) else 1
                sales_channel = weighted_choice(rng, CHANNELS, (42, 31, 18, 9))
                campaign_id = 1
                if ordered_day.month in (3, 4) and rng.random() < 0.35:
                    campaign_id = 2
                elif ordered_day.month in (6, 7) and rng.random() < 0.45:
                    campaign_id = 3
                elif ordered_day.month == 11 and rng.random() < 0.75:
                    campaign_id = 4
                elif sales_channel == "partner" and rng.random() < 0.6:
                    campaign_id = 5
                status = weighted_choice(
                    rng,
                    ("delivered", "shipped", "paid", "refunded", "cancelled"),
                    (70, 12, 8, 6, 4),
                )
                ordered_at = datetime.combine(
                    ordered_day,
                    time(hour=rng.randrange(8, 23), minute=rng.randrange(60)),
                    timezone.utc,
                )
                ship_days = rng.randint(1, 4)
                delivery_days = ship_days + rng.randint(1, 7)
                shipped_at = ordered_at + timedelta(days=ship_days) if status in ("shipped", "delivered", "refunded") else None
                delivered_at = ordered_at + timedelta(days=delivery_days) if status in ("delivered", "refunded") else None
                orders.append(
                    (
                        order_id,
                        resolved_batch_id,
                        customer_id,
                        ordered_at,
                        status,
                        "EUR",
                        sales_channel,
                        weighted_choice(rng, PAYMENT_METHODS, (54, 25, 12, 9)),
                        campaign_id,
                        shipped_at,
                        delivered_at,
                    )
                )
                item_count = weighted_choice(rng, (1, 2, 3, 4, 5), (46, 29, 14, 8, 3))
                for item_offset in range(item_count):
                    category = weighted_choice(
                        rng, categories, category_weights[customer["segment"]]
                    )
                    product = rng.choice(products_by_category[category])
                    campaign_discount = float(CAMPAIGNS[campaign_id - 1][3])
                    discount = min(0.35, campaign_discount + (0.05 if rng.random() < 0.12 else 0))
                    price_noise = rng.uniform(0.96, 1.06)
                    unit_price = round(product[7] * price_noise * seasonal_factor, 2)
                    items.append(
                        (
                            order_id * 10 + item_offset,
                            resolved_batch_id,
                            order_id,
                            product[1],
                            rng.randint(1, 2 if customer["segment"] == "consumer" else 5),
                            unit_price,
                            product[0],
                            product[6],
                            discount,
                        )
                    )

            execute_values(
                cursor,
                """
                INSERT INTO source.orders
                  (order_id, batch_id, customer_id, ordered_at, status, currency,
                   sales_channel, payment_method, campaign_id, shipped_at, delivered_at)
                VALUES %s
                """,
                orders,
            )
            execute_values(
                cursor,
                """
                INSERT INTO source.order_items
                  (order_item_id, batch_id, order_id, sku, quantity, unit_price,
                   product_id, unit_cost, discount_pct)
                VALUES %s
                """,
                items,
            )

    return {
        "batch_id": resolved_batch_id,
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "rows": resolved_rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate an idempotent retail source batch")
    parser.add_argument("--rows", type=int, default=0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--batch-id")
    parser.add_argument(
        "--database-url",
        default=os.environ.get("RETAIL_DATABASE_URL") or os.environ.get("AIRFLOW_CONN_RETAIL_SOURCE"),
    )
    args = parser.parse_args()
    if not args.database_url:
        parser.error("--database-url or RETAIL_DATABASE_URL is required")
    result = generate_batch(args.database_url, args.rows, args.seed, args.batch_id)
    print(result["batch_id"])


if __name__ == "__main__":
    main()
