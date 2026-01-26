# ShopifyQL Syntax Reference

ShopifyQL follows the syntax below. You can place the entire query on one line or on separate lines.

```shopifyql
FROM { table_name }

SHOW { column1 AS { alias } , column2 AS { alias } , ... }

VISUALIZE { column1 AS { alias } , column2 AS { alias } , ... }

  TYPE { visualization_type }

GROUP BY { dimension | date }

  ALL { date }

WHERE { condition }

SINCE { date_offset }

UNTIL { date_offset }

DURING { named_date_range }

COMPARE TO { named_date_range | relative_date_range }

ORDER BY { column } ASC | DESC

LIMIT { number }

-- Single line comment

/*
Multi line comment
*/
```

## Keywords

Keywords need to follow the syntax order, otherwise, errors occur.

### Required keywords

A ShopifyQL query must contain at least the FROM and SHOW keywords.

**Using FROM and SHOW to return a numerical value of net sales**
```shopifyql
FROM orders
SHOW sum(net_sales)
```

### Keyword order

Keywords need to be in the following order:

1. FROM
2. SHOW | VISUALIZE
3. GROUP BY
4. WHERE
5. (SINCE & UNTIL) | DURING
6. COMPARE TO
7. ORDER BY
8. LIMIT

## FROM

```
FROM { table_name }
```

- FROM accepts one parameter, `table_name`, where `table_name` is a table.

## SHOW

```
SHOW { column1 AS { alias } , column2 AS { alias } , ... }
```

- SHOW accepts any number of parameters, where each parameter is a column in a table or an expression.
- Each parameter optionally accepts an alias using the AS keyword.

**Using FROM to return the sum of net sales**
```shopifyql
FROM orders
SHOW sum(net_sales)
```

## AS

```
AS { alias }
```

- AS accepts one parameter, which is an alias for a column name in a table, or an alias for the return value of an aggregate function.
- If an alias has a space in the name, then surround the alias with double quotes.
- AS can used with both the SHOW and VISUALIZE keywords.

**Using AS to alias the sum of net_sales as `Net Sales`**
```shopifyql
FROM orders
SHOW sum(net_sales) AS "Net Sales"
```

**Note:** The double quotes are necessary when the alias contains a space.

## VISUALIZE

```
VISUALIZE { column1 AS { alias } , column2 AS { alias } , ... }
```

- VISUALIZE accepts any number of parameters, where each parameter is a column in a table or an expression.
- Each parameter optionally accepts an alias using the AS keyword.
- VISUALIZE returns axis labels and data formatting information for creating data visualizations.
- Optionally accepts a `visualization_type` using the TYPE keyword.

**Return axis labels and data formatting for the sum of the net sales grouped by month for the last year**
```shopifyql
FROM orders
VISUALIZE sum(net_sales)
TYPE line
GROUP BY month ALL
SINCE -1y
UNTIL today
```

The sales are depicted as a single line, with the x-axis labeled as month, and the y-axis as sum_net_sales.

## TYPE

```
TYPE { visualization_type }
```

- TYPE accepts one parameter, `visualization_type`, where `visualization_type` is `line` or `bar`.
- `line` returns a line graph.
- `bar` returns a bar graph.
- TYPE is an optional keyword. If TYPE isn't used, then ShopifyQL returns a visualization that's appropriate for the submitted query.

## GROUP BY

```
GROUP BY { dimension | date }
```

- GROUP BY accepts any number of parameters, where each is a dimension or time dimension. A dimension is a field in a table.
- Each parameter optionally accepts an alias_name using the AS keyword.
- If there isn't a return value for the specified dimension, expression, or date, then the dimension, expression, or date isn't returned.
- If you want to return the dimension, expression, or date when there's no data present, then you can use the ALL modifier.

**Note:** GROUP BY is similar to the SQL GROUP BY statement.

**Using GROUP BY to sort by shipping country**
```shopifyql
FROM orders
SHOW sum(net_sales)
GROUP BY shipping_country
```

**Using GROUP BY to sort by month**
```shopifyql
FROM orders
SHOW sum(net_sales)
GROUP BY month
```

## ALL

```
GROUP BY { dimension | date } ALL
```

- ALL is an optional GROUP BY modifier which can only be used with a date.
- The ALL modifier fills in zeros for any date where data isn't present.
- The ALL modifier enables you to retrieve continuous date periods. This allows you to get continuous date periods without having to perform joins to date lookup tables.
- When using the ALL modifier SINCE or DURING must also be specified.

**Using GROUP BY with ALL modifier to retrieve the net sales for each hour in the last 24 hours**
```shopifyql
FROM orders
SHOW sum(net_sales)
GROUP BY hour ALL
SINCE -1d
UNTIL today
ORDER BY hour DESC
```

## WHERE

```
WHERE { condition }
```

- WHERE accepts one parameter, `condition`, where `condition` is an expression that consists of one or more comparison operators and logical operators.
- WHERE filters the results of an entire query based on the specified condition.

**Using WHERE and the = operator to filter the gross sales for all orders that were shipped to the United States**
```shopifyql
FROM orders
SHOW sum(gross_sales)
WHERE shipping_country = 'United States'
```

## SINCE and UNTIL

```
SINCE { date_offset }
```

- SINCE accepts one parameter, `date_offset`, where `date_offset` is a date range operator.
- The date range operator that's used for `start_date_offset` sets a starting date in a date range. This date is included in the range.

```
UNTIL { date_offset }
```

- UNTIL accepts one parameter, `date_offset`, where `date_offset` is a date range operator.
- The date range operator that's used for `end_date_offset` sets an ending date in a date range. This date is included in the range.
- If UNTIL isn't used in a query, then `today` is used as the ending date.

**Using SINCE and UNTIL to filter the net sales since and including 30 days ago until and including yesterday**
```shopifyql
FROM orders
SHOW sum(net_sales)
SINCE -30d
UNTIL yesterday
```

## DURING

```
DURING { named_date_range }
```

- DURING accepts one parameter, `named_date_range`, where `named_date_range` is a named date range operator.
- DURING is an optional keyword that replaces SINCE and UNTIL statements.
- This keyword helps to filter the query results for known time periods such as a calendar year or a specific month, or to filter the query results for date ranges that have different dates every year, such as Black Friday Cyber Monday.

**Using DURING to filter the net sales during Black Friday Cyber Monday 2021**
```shopifyql
FROM orders
SHOW sum(net_sales)
GROUP BY day
DURING bfcm2021
```

## COMPARE TO

```
COMPARE TO { named_date_range | relative_date_range }
```

- COMPARE TO is an optional keyword which is paired with SINCE and UNTIL or DURING.
- When paired with SINCE and UNTIL COMPARE TO accepts a `relative_date_range`.
- While using the `relative_date_range` `previous_year` the SINCE and UNTIL specified length of time must be a year or less.
- When paired with DURING, COMPARE TO accepts either a `named_date_range` or a `relative_date_range`.
- While using a `named_date_range` it must match the length of the parameter in DURING.
- This keyword allows you to compare data across the `date_offset` in SINCE and UNTIL or DURING to the COMPARE TO `named_date_range` or `relative_date_range`.

**Using DURING and COMPARE TO to compare the net sales during Black Friday Cyber Monday 2022 and Black Friday Cyber Monday 2021**
```shopifyql
FROM orders
SHOW sum(net_sales)
GROUP BY day
DURING bfcm2022
COMPARE TO bfcm2021
```

## ORDER BY

```
ORDER BY { column } ASC | DESC
```

- ORDER BY can accept a list of one or more parameters. Each parameter consists of one or two elements, `column`, and an optional ASC or DESC.
- `column` is a column in a table, and ASC or DESC change the behavior of the returned results.
- The ASC parameter is used after the column parameter, and indicates that the returned query results are sorted in an ascending order.
- The DESC parameter is used after the column parameter, and indicates that the returned query results are sorted in a descending order.
- If the ASC or DESC parameters aren't used, then the default sorting order is ascending.
- If ORDER BY has multiple columns, then the results are first sorted by the first column, and then sorted by the second column, and so on.
- The columns used in the ORDER BY parameters must be present in either the SHOW, BY or OVER parameter list.

**Using ORDER BY to retrieve the net sales for each product**
```shopifyql
FROM products
SHOW sum(net_sales) as sales
GROUP BY product_title
ORDER BY sales DESC
```

## LIMIT

```
LIMIT { number }
```

- LIMIT accepts one parameter, `number`, where `number` is a number that represents how many rows that you want the query to return.
- LIMIT enables you to understand the data in each column without returning all of the data in the table.
- This is useful for larger tables where queries can take longer to return values.
- You can also use LIMIT with ORDER BY to create lists of the top or bottom-most X. For example, the top five products.

**Using LIMIT with ORDER BY to create a list of the top-10 selling products over the last 3 months**
```shopifyql
FROM products
SHOW sum(gross_sales) as total_gross_sales
GROUP BY product_title
SINCE -3m
UNTIL today
ORDER BY total_gross_sales DESC
LIMIT 10
```

## Time dimensions

The time functions are abstracted so you don't have to keep track of which date field corresponds to the grain of the available datasets. The following date fields are available as time dimensions in ShopifyQL:

| Date field | Description |
|------------|-------------|
| hour | Groups by hour of calendar day |
| day | Groups by calendar day |
| week | Groups by calendar week |
| month | Groups by calendar month |
| quarter | Groups by calendar quarter |
| year | Groups by calendar year |
| hour_of_day | Groups by 24 hours (1, 2, ..., 24) |
| day_of_week | Groups by day of week (M, T, W, ..., S) |
| week_of_year | Groups by week of year (1, 2, ..., 52) |

## Date range operators

You can use the following date range operators as well as a named date range operator in SINCE and UNTIL statements.

| Date range operator | Description |
|---------------------|-------------|
| {-} {#} d | The number of calendar days ago from the day that the query was run |
| {-} {#} w | The number of calendar weeks ago from the day that the query was run |
| {-} {#} m | The number of calendar months ago from the day that the query was run |
| {-} {#} q | The number of calendar quarters ago from the day that the query was run |
| {-} {#} y | The number of calendar years ago from the day that the query was run |
| yyyy-mm-dd | A specific date |

**Note:** Date range operators truncate to the start of the time grain (day, week, month, quarter, and year) when used with SINCE and to the end of the time grain when used with UNTIL.

## Named date range operators

SINCE and UNTIL, DURING, and COMPARE TO accept any of the following named date range date operators:

| Date Range Operator | Description |
|---------------------|-------------|
| today | The day that the query was run |
| yesterday | The previous 24-hour period from the time that the query was run |
| this_week | The current calendar week |
| this_month | The current calendar month |
| this_quarter | The current calendar quarter |
| this_year | The current calendar year |
| last_week | The previous calendar week |
| last_month | The previous calendar month |
| last_quarter | The previous calendar quarter |
| last_year | The previous calendar year |
| bfcm2022 | November 25 to November 28 2022 |
| bfcm2021 | November 26 to November 29 2021 |
| bfcm2020 | November 27 to November 30 2020 |
| bfcm2019 | November 29 to December 2 2019 |
| bfcm2018 | November 23 to November 26 2018 |
| bfcm2017 | November 24 to November 27 2017 |
| bfcm2016 | November 25 to November 28 2016 |

## Relative date range operators

Relative operators return the same length of time as the base date range, shifted back by the specified period. COMPARE TO accepts the following relative date range operators:

| Date Range Operator | Description |
|---------------------|-------------|
| previous_period | One period before the base date range |
| previous_year | One year before the base date range |

## Comparison operators

You can use the following comparison operators in WHERE statements.

| Comparison operator | Description |
|---------------------|-------------|
| = | Equal to |
| != | Not equal to |
| < | Less than |
| > | Greater than |
| <= | Less than or equal to |
| >= | Greater than or equal to |

## Logical operators

You can use one or more of the following logical operators in WHERE statements.

| Logical operator | Description |
|------------------|-------------|
| AND | Return all rows where the conditions that are separated by an AND are satisfied |
| OR | Return all rows where either of the conditions that are separated by an OR are satisfied |
| NOT | Return all rows where the conditions aren't satisfied |

## Mathematical operators

You can use the following mathematical operators on numerical data.

| Mathematical operator | Description |
|-----------------------|-------------|
| + | Add two numbers |
| - | Subtract two numbers |
| * | Multiple two numbers |
| / | Divide two numbers |

## Aggregate functions

You can use the following functions to aggregate columns, and group columns by dimensions.

| Aggregate function | Description |
|--------------------|-------------|
| count() | Return the number of instances in a result set |
| sum() | Return the sum of values in a result set |
| min() | Return the lowest value in a result set |
| max() | Return the highest value in a result set |
| avg() | Return the average value in a result set |

The `sum()`, `min()`, `max()`, and `avg()` functions can only be used with numerical values, while `count()` can be used to count different instances of dimensional attributes. You can't use aggregated fields as arguments in the functions.

## Comments

- Single line comments start with `--` and end at the end of the line.
- Multi-line comments start with `/*` and end with `*/`.

You can use comments to explain sections of ShopifyQL statements, or to prevent the execution of a ShopifyQL statement. Any text within a comment will be ignored during execution time.

**Using comments to prevent execution of statements or add explanations**
```shopifyql
FROM orders
SHOW sum(net_sales), sum(ordered_product_quantity), count(billing_city) AS number_of_cities, average_order_value
-- the line below has been commented out and will not run
-- GROUP BY billing_region
WHERE billing_country = 'United States'
/*
this line and the two lines below it have been commented out and will not run
SINCE 2021-01-01
UNTIL 2021-12-31
*/
```
