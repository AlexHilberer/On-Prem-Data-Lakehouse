import json
import os

from sqlalchemy import func
from superset import db
from superset.app import create_app


DATASETS = {
    "Sales": {
        "description": "Order-line commerce performance served by Cube Core",
        "columns": {
            "orderDate": ("TIMESTAMP", True),
            "country": ("TEXT", False),
            "city": ("TEXT", False),
            "region": ("TEXT", False),
            "customerSegment": ("TEXT", False),
            "acquisitionChannel": ("TEXT", False),
            "salesChannel": ("TEXT", False),
            "paymentMethod": ("TEXT", False),
            "campaignName": ("TEXT", False),
            "status": ("TEXT", False),
            "sku": ("TEXT", False),
            "productName": ("TEXT", False),
            "category": ("TEXT", False),
            "subcategory": ("TEXT", False),
            "brand": ("TEXT", False),
            "revenue": ("NUMERIC", False),
            "grossProfit": ("NUMERIC", False),
            "grossSales": ("NUMERIC", False),
            "discountAmount": ("NUMERIC", False),
            "refundAmount": ("NUMERIC", False),
            "unitsSold": ("NUMERIC", False),
            "orderCount": ("NUMERIC", False),
            "customerCount": ("NUMERIC", False),
            "averageOrderValue": ("NUMERIC", False),
            "grossMargin": ("NUMERIC", False),
            "refundRate": ("NUMERIC", False),
            "averageFulfillmentDays": ("NUMERIC", False),
        },
        "metrics": {
            "revenue": 'SUM("revenue")',
            "gross_profit": 'SUM("grossProfit")',
            "orders": 'COUNT(DISTINCT "orderCount")',
            "customers": 'COUNT(DISTINCT "customerCount")',
            "units": 'SUM("unitsSold")',
            "aov": 'AVG("averageOrderValue")',
            "gross_margin": 'AVG("grossMargin")',
            "refund_rate": 'AVG("refundRate")',
            "fulfillment_days": 'AVG("averageFulfillmentDays")',
        },
    },
    "Products": {
        "description": "Daily product and channel performance served by Cube Core",
        "columns": {
            "orderDate": ("TIMESTAMP", True),
            "sku": ("TEXT", False),
            "productName": ("TEXT", False),
            "category": ("TEXT", False),
            "subcategory": ("TEXT", False),
            "brand": ("TEXT", False),
            "salesChannel": ("TEXT", False),
            "revenue": ("NUMERIC", False),
            "grossProfit": ("NUMERIC", False),
            "discountAmount": ("NUMERIC", False),
            "unitsSold": ("NUMERIC", False),
            "orderCount": ("NUMERIC", False),
            "grossMargin": ("NUMERIC", False),
        },
        "metrics": {
            "revenue": 'SUM("revenue")',
            "gross_profit": 'SUM("grossProfit")',
            "units": 'SUM("unitsSold")',
            "orders": 'SUM("orderCount")',
            "gross_margin": 'AVG("grossMargin")',
        },
    },
    "Customers": {
        "description": "Governed customer value and repeat behavior served by Cube Core",
        "columns": {
            "fullName": ("TEXT", False),
            "email": ("TEXT", False),
            "country": ("TEXT", False),
            "city": ("TEXT", False),
            "region": ("TEXT", False),
            "customerSegment": ("TEXT", False),
            "acquisitionChannel": ("TEXT", False),
            "firstOrderDate": ("TIMESTAMP", True),
            "lastOrderDate": ("TIMESTAMP", True),
            "isRepeatCustomer": ("BOOLEAN", False),
            "customerCount": ("NUMERIC", False),
            "lifetimeValue": ("NUMERIC", False),
            "grossProfit": ("NUMERIC", False),
            "orderCount": ("NUMERIC", False),
            "unitsPurchased": ("NUMERIC", False),
            "refundAmount": ("NUMERIC", False),
            "repeatCustomers": ("NUMERIC", False),
            "repeatRate": ("NUMERIC", False),
            "averageLifetimeValue": ("NUMERIC", False),
        },
        "metrics": {
            "customers": 'COUNT(DISTINCT "customerCount")',
            "lifetime_value": 'SUM("lifetimeValue")',
            "orders": 'SUM("orderCount")',
            "repeat_customers": 'COUNT(DISTINCT "repeatCustomers")',
            "repeat_rate": 'AVG("repeatRate")',
            "average_ltv": 'AVG("averageLifetimeValue")',
        },
    },
}


CHARTS = [
    ("Total Revenue", "Sales", "big_number_total", {"metric": "revenue", "subheader": "Net recognized sales"}),
    ("Gross Profit", "Sales", "big_number_total", {"metric": "gross_profit", "subheader": "After product costs"}),
    ("Total Orders", "Sales", "big_number_total", {"metric": "orders", "subheader": "Distinct orders"}),
    ("Average Order Value", "Sales", "big_number_total", {"metric": "aov", "subheader": "Revenue per order"}),
    ("Revenue & Profit Trend", "Sales", "echarts_timeseries_line", {"metrics": ["revenue", "gross_profit"], "granularity_sqla": "orderDate", "time_grain_sqla": "P1M"}),
    ("Revenue by Country", "Sales", "echarts_timeseries_bar", {"metrics": ["revenue"], "groupby": ["country"], "granularity_sqla": "orderDate", "time_grain_sqla": "P1M"}),
    ("Sales Channel Mix", "Sales", "pie", {"metric": "revenue", "groupby": ["salesChannel"], "donut": True}),
    ("Category Contribution", "Sales", "treemap_v2", {"metric": "revenue", "groupby": ["category"]}),
    ("Product Revenue Trend", "Products", "echarts_timeseries_line", {"metrics": ["revenue"], "groupby": ["category"], "granularity_sqla": "orderDate", "time_grain_sqla": "P1M"}),
    ("Revenue by Category", "Products", "echarts_timeseries_bar", {"metrics": ["revenue", "gross_profit"], "x_axis": "category", "groupby": []}),
    ("Brand Performance", "Products", "pie", {"metric": "revenue", "groupby": ["brand"], "donut": True}),
    ("Top Products", "Products", "table", {"metrics": ["revenue", "gross_profit", "units", "orders"], "groupby": ["productName", "category", "brand"], "row_limit": 15}),
    ("Channel Product Mix", "Products", "echarts_timeseries_bar", {"metrics": ["revenue"], "x_axis": "salesChannel", "groupby": ["category"]}),
    ("Discount vs Margin", "Products", "table", {"metrics": ["revenue", "gross_profit", "gross_margin"], "groupby": ["category", "brand"], "row_limit": 30}),
    ("Customer Lifetime Value", "Customers", "big_number_total", {"metric": "lifetime_value", "subheader": "Value of generated customer base"}),
    ("Repeat Customer Rate", "Customers", "big_number_total", {"metric": "repeat_rate", "subheader": "Customers with multiple orders"}),
    ("Customers by Segment", "Customers", "pie", {"metric": "customers", "groupby": ["customerSegment"], "donut": True}),
    ("Acquisition Performance", "Customers", "echarts_timeseries_bar", {"metrics": ["customers", "lifetime_value"], "x_axis": "acquisitionChannel", "groupby": []}),
    ("Order Status", "Sales", "pie", {"metric": "orders", "groupby": ["status"], "donut": True}),
    ("Fulfillment by Country", "Sales", "echarts_timeseries_bar", {"metrics": ["fulfillment_days"], "x_axis": "country", "groupby": []}),
    ("Customer Detail", "Customers", "table", {"metrics": ["lifetime_value", "orders"], "groupby": ["fullName", "email", "country", "customerSegment"], "row_limit": 25}),
]


DASHBOARDS = {
    "executive-commerce": (
        "Executive Commerce",
        ["Total Revenue", "Gross Profit", "Total Orders", "Average Order Value",
         "Revenue & Profit Trend", "Revenue by Country", "Sales Channel Mix", "Category Contribution"],
    ),
    "product-sales": (
        "Product & Sales",
        ["Product Revenue Trend", "Revenue by Category", "Brand Performance",
         "Top Products", "Channel Product Mix", "Discount vs Margin"],
    ),
    "customer-operations": (
        "Customer & Operations",
        ["Customer Lifetime Value", "Repeat Customer Rate", "Customers by Segment",
         "Acquisition Performance", "Order Status", "Fulfillment by Country", "Customer Detail"],
    ),
}


THEME_CSS = """
.dashboard-content { background: #0b1220; }
.dashboard-header { background: #111a2b; border-bottom: 1px solid #25324a; }
.dashboard-component-chart-holder { background: #111a2b; border: 1px solid #25324a;
  border-radius: 12px; box-shadow: 0 8px 24px rgba(0,0,0,.22); }
.dashboard-component-chart-holder:hover { border-color: #22d3ee; }
.chart-header .header-title { color: #e5edf8; font-weight: 600; }
"""


def layout_for(charts):
    position = {
        "DASHBOARD_VERSION_KEY": "v2",
        "ROOT_ID": {"id": "ROOT_ID", "type": "ROOT", "children": ["GRID_ID"]},
        "GRID_ID": {"id": "GRID_ID", "type": "GRID", "parents": ["ROOT_ID"], "children": []},
    }
    row_index = -1
    row_width = 0
    for chart in charts:
        chart_width = 3 if chart.viz_type == "big_number_total" else 6
        if row_width == 0 or row_width + chart_width > 12:
            row_index += 1
            row_width = 0
        row_id = f"ROW-{row_index}"
        if row_id not in position:
            position[row_id] = {
                "id": row_id,
                "type": "ROW",
                "parents": ["ROOT_ID", "GRID_ID"],
                "children": [],
                "meta": {"background": "BACKGROUND_TRANSPARENT"},
            }
            position["GRID_ID"]["children"].append(row_id)
        chart_id = f"CHART-{chart.id}"
        position[chart_id] = {
            "id": chart_id,
            "type": "CHART",
            "parents": ["ROOT_ID", "GRID_ID", row_id],
            "children": [],
            "meta": {
                "chartId": chart.id,
                "sliceName": chart.slice_name,
                "width": chart_width,
                "height": 18 if chart_width == 3 else 38,
            },
        }
        position[row_id]["children"].append(chart_id)
        row_width += chart_width
    return json.dumps(position)


def native_filters(dataset):
    filters = []
    for index, (name, column) in enumerate(
        (("Date", "orderDate"), ("Country", "country"), ("Channel", "salesChannel"))
    ):
        if column not in {item.column_name for item in dataset.columns}:
            continue
        filters.append(
            {
                "id": f"NATIVE_FILTER-{index + 1}",
                "name": name,
                "filterType": "filter_time" if column == "orderDate" else "filter_select",
                "targets": [{"datasetId": dataset.id, "column": {"name": column}}],
                "defaultDataMask": {"filterState": {}, "extraFormData": {}},
                "controlValues": {"enableEmptyFilter": True, "multiSelect": True},
                "scope": {"rootPath": ["ROOT_ID"], "excluded": []},
                "cascadeParentIds": [],
            }
        )
    return filters


app = create_app()
with app.app_context():
    from superset.connectors.sqla.models import SqlaTable, SqlMetric, TableColumn
    from superset.models.core import Database
    from superset.models.dashboard import Dashboard
    from superset.models.slice import Slice

    database = db.session.query(Database).filter_by(database_name="Cube").one_or_none()
    if database is None:
        database = Database(
            database_name="Cube",
            sqlalchemy_uri=(
                "postgresql+psycopg2://superset:"
                f"{os.environ['CUBE_SQL_PASSWORD']}@cube:15432/cube"
            ),
            expose_in_sqllab=True,
            allow_run_async=False,
        )
        db.session.add(database)
        db.session.flush()

    datasets = {}
    for dataset_name, specification in DATASETS.items():
        dataset = (
            db.session.query(SqlaTable)
            .filter(
                SqlaTable.database_id == database.id,
                func.lower(SqlaTable.table_name) == dataset_name.lower(),
            )
            .one_or_none()
        )
        if dataset is None:
            dataset = SqlaTable(
                database_id=database.id,
                table_name=dataset_name,
                schema="public",
            )
            db.session.add(dataset)
            db.session.flush()
        dataset.description = specification["description"]
        existing_columns = {column.column_name for column in dataset.columns}
        for column_name, (column_type, is_temporal) in specification["columns"].items():
            if column_name not in existing_columns:
                db.session.add(
                    TableColumn(
                        column_name=column_name,
                        type=column_type,
                        is_dttm=is_temporal,
                        groupby=True,
                        filterable=True,
                        table=dataset,
                    )
                )
        existing_metrics = {metric.metric_name: metric for metric in dataset.metrics}
        for metric_name, expression in specification["metrics"].items():
            metric = existing_metrics.get(metric_name)
            if metric is None:
                metric = SqlMetric(metric_name=metric_name, table=dataset)
                db.session.add(metric)
            metric.expression = expression
        datasets[dataset_name] = dataset
    db.session.flush()

    charts = {}
    for chart_name, dataset_name, viz_type, parameters in CHARTS:
        dataset = datasets[dataset_name]
        chart = db.session.query(Slice).filter_by(slice_name=chart_name).one_or_none()
        if chart is None:
            chart = Slice(
                slice_name=chart_name,
                viz_type=viz_type,
                datasource_type="table",
                datasource_id=dataset.id,
            )
            db.session.add(chart)
        chart.viz_type = viz_type
        chart.datasource_type = "table"
        chart.datasource_id = dataset.id
        chart.params = json.dumps(
            {
                "viz_type": viz_type,
                "datasource": f"{dataset.id}__table",
                "adhoc_filters": [],
                "row_limit": 1000,
                "color_scheme": "supersetColors",
                "show_legend": True,
                "rich_tooltip": True,
                "show_value": True,
                "number_format": "€,.2f",
                **parameters,
            }
        )
        charts[chart_name] = chart
    db.session.flush()

    obsolete = db.session.query(Dashboard).filter_by(slug="retail-overview").one_or_none()
    if obsolete is not None:
        db.session.delete(obsolete)

    for slug, (title, chart_names) in DASHBOARDS.items():
        dashboard = db.session.query(Dashboard).filter_by(slug=slug).one_or_none()
        if dashboard is None:
            dashboard = Dashboard(slug=slug)
            db.session.add(dashboard)
        selected_charts = [charts[name] for name in chart_names]
        dashboard.dashboard_title = title
        dashboard.published = True
        dashboard.slices = selected_charts
        dashboard.position_json = layout_for(selected_charts)
        filter_dataset = {
            "executive-commerce": datasets["Sales"],
            "product-sales": datasets["Products"],
            "customer-operations": datasets["Customers"],
        }[slug]
        dashboard.json_metadata = json.dumps(
            {
                "color_scheme": "supersetColors",
                "refresh_frequency": 0,
                "timed_refresh_immune_slices": [],
                "native_filter_configuration": native_filters(filter_dataset),
            }
        )
        if hasattr(dashboard, "css"):
            dashboard.css = THEME_CSS

    db.session.commit()
