cube(`Customers`, {
  sql: `SELECT * FROM lakehouse.gold.customer_360`,

  measures: {
    customerCount: { sql: `customer_id`, type: `countDistinct` },
    lifetimeValue: { sql: `lifetime_value`, type: `sum`, format: `currency` },
    grossProfit: { sql: `gross_profit`, type: `sum`, format: `currency` },
    orderCount: { sql: `order_count`, type: `sum` },
    unitsPurchased: { sql: `units_purchased`, type: `sum` },
    refundAmount: { sql: `refund_amount`, type: `sum`, format: `currency` },
    repeatCustomers: {
      sql: `CASE WHEN is_repeat_customer THEN customer_id END`,
      type: `countDistinct`
    },
    repeatRate: {
      sql: `100.0 * ${repeatCustomers} / NULLIF(${customerCount}, 0)`,
      type: `number`,
      format: `percent`
    },
    averageLifetimeValue: {
      sql: `${lifetimeValue} / NULLIF(${customerCount}, 0)`,
      type: `number`,
      format: `currency`
    }
  },

  dimensions: {
    id: {
      sql: `customer_id`,
      type: `number`,
      primaryKey: true
    },
    customerId: { sql: `customer_id`, type: `number` },
    fullName: { sql: `full_name`, type: `string` },
    email: { sql: `email`, type: `string` },
    country: { sql: `country`, type: `string` },
    city: { sql: `city`, type: `string` },
    region: { sql: `region`, type: `string` },
    customerSegment: { sql: `customer_segment`, type: `string` },
    acquisitionChannel: { sql: `acquisition_channel`, type: `string` },
    firstOrderDate: { sql: `CAST(first_order_date AS timestamp)`, type: `time` },
    lastOrderDate: { sql: `CAST(last_order_date AS timestamp)`, type: `time` },
    isRepeatCustomer: { sql: `is_repeat_customer`, type: `boolean` }
  }
});
