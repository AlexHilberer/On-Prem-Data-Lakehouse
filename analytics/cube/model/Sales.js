cube(`Sales`, {
  sql: `SELECT * FROM lakehouse.gold.sales_performance`,

  measures: {
    revenue: { sql: `revenue`, type: `sum`, format: `currency` },
    grossSales: { sql: `gross_sales`, type: `sum`, format: `currency` },
    grossProfit: { sql: `gross_profit`, type: `sum`, format: `currency` },
    discountAmount: { sql: `discount_amount`, type: `sum`, format: `currency` },
    refundAmount: { sql: `refund_amount`, type: `sum`, format: `currency` },
    unitsSold: { sql: `quantity`, type: `sum` },
    orderCount: { sql: `order_id`, type: `countDistinct` },
    customerCount: { sql: `customer_id`, type: `countDistinct` },
    refundedOrders: {
      sql: `CASE WHEN status = 'refunded' THEN order_id END`,
      type: `countDistinct`
    },
    averageOrderValue: {
      sql: `${revenue} / NULLIF(${orderCount}, 0)`,
      type: `number`,
      format: `currency`
    },
    grossMargin: {
      sql: `100.0 * ${grossProfit} / NULLIF(${revenue}, 0)`,
      type: `number`,
      format: `percent`
    },
    refundRate: {
      sql: `100.0 * ${refundedOrders} / NULLIF(${orderCount}, 0)`,
      type: `number`,
      format: `percent`
    },
    averageFulfillmentDays: {
      sql: `fulfillment_days`,
      type: `avg`
    }
  },

  dimensions: {
    id: { sql: `order_item_id`, type: `number`, primaryKey: true },
    orderDate: { sql: `CAST(order_date AS timestamp)`, type: `time` },
    orderId: { sql: `order_id`, type: `number` },
    customerId: { sql: `customer_id`, type: `number` },
    country: { sql: `country`, type: `string` },
    city: { sql: `city`, type: `string` },
    region: { sql: `region`, type: `string` },
    customerSegment: { sql: `customer_segment`, type: `string` },
    acquisitionChannel: { sql: `acquisition_channel`, type: `string` },
    salesChannel: { sql: `sales_channel`, type: `string` },
    paymentMethod: { sql: `payment_method`, type: `string` },
    campaignName: { sql: `campaign_name`, type: `string` },
    status: { sql: `status`, type: `string` },
    sku: { sql: `sku`, type: `string` },
    productName: { sql: `product_name`, type: `string` },
    category: { sql: `category`, type: `string` },
    subcategory: { sql: `subcategory`, type: `string` },
    brand: { sql: `brand`, type: `string` }
  }
});
