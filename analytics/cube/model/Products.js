cube(`Products`, {
  sql: `SELECT * FROM lakehouse.gold.product_performance`,

  measures: {
    revenue: { sql: `revenue`, type: `sum`, format: `currency` },
    grossProfit: { sql: `gross_profit`, type: `sum`, format: `currency` },
    discountAmount: { sql: `discount_amount`, type: `sum`, format: `currency` },
    unitsSold: { sql: `units_sold`, type: `sum` },
    orderCount: { sql: `order_count`, type: `sum` },
    grossMargin: {
      sql: `100.0 * ${grossProfit} / NULLIF(${revenue}, 0)`,
      type: `number`,
      format: `percent`
    }
  },

  dimensions: {
    id: {
      sql: `concat(cast(order_date as varchar), '-', cast(product_id as varchar), '-', sales_channel)`,
      type: `string`,
      primaryKey: true
    },
    orderDate: { sql: `CAST(order_date AS timestamp)`, type: `time` },
    productId: { sql: `product_id`, type: `number` },
    sku: { sql: `sku`, type: `string` },
    productName: { sql: `product_name`, type: `string` },
    category: { sql: `category`, type: `string` },
    subcategory: { sql: `subcategory`, type: `string` },
    brand: { sql: `brand`, type: `string` },
    salesChannel: { sql: `sales_channel`, type: `string` }
  }
});
