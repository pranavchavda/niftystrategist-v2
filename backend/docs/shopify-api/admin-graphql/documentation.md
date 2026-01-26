---
title: GraphQL Admin API reference
description: The Admin API lets you build apps and integrations that extend and enhance the Shopify admin. Learn how to get started using efficient GraphQL queries.
api_version: 2025-10
api_name: admin
source_url:
  html: https://shopify.dev/docs/api/admin-graphql/latest
  md: https://shopify.dev/docs/api/admin-graphql/latest.md
---

# GraphQL Admin API reference

The Admin API lets you build apps and integrations that extend and enhance the Shopify admin.

This page will help you get up and running with Shopify’s GraphQL API.

## Client libraries

Use Shopify’s officially supported libraries to build fast, reliable apps with the programming languages and frameworks you already know.

React Router

The official package for React Router applications.

* [Docs](https://shopify.dev/docs/api/shopify-app-react-router)
* [npm package](https://www.npmjs.com/package/@shopify/shopify-app-react-router)
* [GitHub repo](https://github.com/Shopify/shopify-app-js/tree/main/packages/apps/shopify-app-react-router#readme)

Node.js

The official client library for Node.js apps. No framework dependencies—works with any Node.js app.

* [Docs](https://github.com/Shopify/shopify-app-js/tree/main/packages/apps/shopify-api#readme)
* [npm package](https://www.npmjs.com/package/@shopify/shopify-api)
* [GitHub repo](https://github.com/Shopify/shopify-app-js/tree/main/packages/apps/shopify-api)

Ruby

The official client library for Ruby apps.

* [Docs](https://shopify.github.io/shopify-api-ruby/)

* [Ruby gem](https://rubygems.org/gems/shopify_api)

* [GitHub repo](https://github.com/Shopify/shopify-api-ruby)

cURL

Use the [curl utility](https://curl.se/) to make API queries directly from the command line.

Other

Need a different language? Check the list of [community-supported libraries](https://shopify.dev/apps/tools/api-libraries#third-party-admin-api-libraries).

```bash
npm install -g @shopify/cli@latest
shopify app init
```

```ts
npm install --save @shopify/shopify-api

# or
yarn add @shopify/shopify-api
```

```ruby
bundle add shopify_api
```

```bash

# cURL is often available by default on macOS and Linux.

# See http://curl.se/docs/install.html for more details.
```

##### React Router

```
npm install -g @shopify/cli@latest
shopify app init
```

##### Node.js

```
npm install --save @shopify/shopify-api

# or
yarn add @shopify/shopify-api
```

##### Ruby

```
bundle add shopify_api
```

##### cURL

```

# cURL is often available by default on macOS and Linux.

# See http://curl.se/docs/install.html for more details.
```

***

## Authentication

All GraphQL Admin API requests require a valid Shopify access token. If you use Shopify’s [client libraries](https://shopify.dev/apps/tools/api-libraries), then this will be done for you. Otherwise, you should include your token as a `X-Shopify-Access-Token` header on all GraphQL requests.

Public and custom apps created in the Partner Dashboard generate tokens using [OAuth](https://shopify.dev/apps/auth/oauth), and custom apps made in the Shopify admin are [authenticated in the Shopify admin](https://shopify.dev/apps/auth/admin-app-access-tokens).

To keep the platform secure, apps need to request specific [access scopes](https://shopify.dev/api/usage/access-scopes) during the install process. Only request as much data access as your app needs to work.

Learn more about [getting started with authentication](https://shopify.dev/apps/auth) and [building apps](https://shopify.dev/apps/getting-started).

```js
import { authenticate } from "../shopify.server";


export async function loader({request}) {
  const { admin } = await authenticate.admin(request);
  const response = await admin.graphql(
    `query { shop { name } }`,
  );
}
```

```ts
const client = new shopify.clients.Graphql({session});
const response = await client.query({data: 'query { shop { name } }'});
```

```ruby
session = ShopifyAPI::Auth::Session.new(
  shop: 'your-development-store.myshopify.com',
  access_token: access_token,
)
client = ShopifyAPI::Clients::Graphql::Admin.new(
  session: session,
)
response = client.query(query: 'query { shop { name } }')
```

```bash

# Replace {SHOPIFY_ACCESS_TOKEN} with your actual access token
  curl -X POST \
  https://{shop}.myshopify.com/admin/api/2025-10/graphql.json \
  -H 'Content-Type: application/json' \
  -H 'X-Shopify-Access-Token: {SHOPIFY_ACCESS_TOKEN}' \
  -d '{
  "query": "query { shop { name } }"
  }'
```

##### React Router

```
import { authenticate } from "../shopify.server";

export async function loader({request}) {
  const { admin } = await authenticate.admin(request);
  const response = await admin.graphql(
    `query { shop { name } }`,
  );
}
```

##### Node.js

```
const client = new shopify.clients.Graphql({session});
const response = await client.query({data: 'query { shop { name } }'});
```

##### Ruby

```
session = ShopifyAPI::Auth::Session.new(
  shop: 'your-development-store.myshopify.com',
  access_token: access_token,
)
client = ShopifyAPI::Clients::Graphql::Admin.new(
  session: session,
)
response = client.query(query: 'query { shop { name } }')
```

##### cURL

```

# Replace {SHOPIFY_ACCESS_TOKEN} with your actual access token
  curl -X POST \
  https://{shop}.myshopify.com/admin/api/2025-10/graphql.json \
  -H 'Content-Type: application/json' \
  -H 'X-Shopify-Access-Token: {SHOPIFY_ACCESS_TOKEN}' \
  -d '{
  "query": "query { shop { name } }"
  }'
```

***

## Endpoints and queries

GraphQL queries are executed by sending `POST` HTTP requests to the endpoint:

`https://{store_name}.myshopify.com/admin/api/2025-10/graphql.json`

Queries begin with one of the objects listed under [QueryRoot](https://shopify.dev/api/admin-graphql/2025-10/objects/queryroot). The QueryRoot is the schema’s entry-point for queries.

Queries are equivalent to making a `GET` request in REST. The example shown is a query to get the ID and title of the first three products.

Learn more about [API usage](https://shopify.dev/api/usage).

***

Note

Explore and learn Shopify's Admin API using [GraphiQL Explorer](https://shopify.dev/apps/tools/graphiql-admin-api). To build queries and mutations with shop data, install [Shopify’s GraphiQL app](https://shopify-graphiql-app.shopifycloud.com/).

POST

## https://{store\_name}.myshopify.com/admin/api/2025-10/graphql.json

```ts
import { authenticate } from "../shopify.server";


export async function loader({request}) {
  const { admin } = await authenticate.admin(request);
  const response = await admin.graphql(
    `#graphql
    query getProducts {
      products (first: 3) {
        edges {
          node {
            id
            title
          }
        }
      }
    }`,
  );
  const json = await response.json();
  return { products: json?.data?.products?.edges };
}
```

```ts
const queryString = `{
  products (first: 3) {
    edges {
      node {
        id
        title
      }
    }
  }
}`


// `session` is built as part of the OAuth process
const client = new shopify.clients.Graphql({session});
const products = await client.query({
  data: queryString,
});
```

```ruby
query = <<~GQL
  {
    products (first: 3) {
      edges {
        node {
          id
          title
        }
      }
    }
  }
GQL

# session is built as part of the OAuth process
client = ShopifyAPI::Clients::Graphql::Admin.new(
  session: session
)
products = client.query(
  query: query,
)
```

```bash

# Get the ID and title of the three most recently added products
curl -X POST   https://{store_name}.myshopify.com/admin/api/2025-10/graphql.json \
  -H 'Content-Type: application/json' \
  -H 'X-Shopify-Access-Token: {access_token}' \
  -d '{
  "query": "{
    products(first: 3) {
      edges {
        node {
          id
          title
        }
      }
    }
  }"
}'
```

##### React Router

```
import { authenticate } from "../shopify.server";

export async function loader({request}) {
  const { admin } = await authenticate.admin(request);
  const response = await admin.graphql(
    `#graphql
    query getProducts {
      products (first: 3) {
        edges {
          node {
            id
            title
          }
        }
      }
    }`,
  );
  const json = await response.json();
  return { products: json?.data?.products?.edges };
}
```

##### Node.js

```
const queryString = `{
  products (first: 3) {
    edges {
      node {
        id
        title
      }
    }
  }
}`

// `session` is built as part of the OAuth process
const client = new shopify.clients.Graphql({session});
const products = await client.query({
  data: queryString,
});
```

##### Ruby

```
query = <<~GQL
  {
    products (first: 3) {
      edges {
        node {
          id
          title
        }
      }
    }
  }
GQL

# session is built as part of the OAuth process
client = ShopifyAPI::Clients::Graphql::Admin.new(
  session: session
)
products = client.query(
  query: query,
)
```

##### cURL

```

# Get the ID and title of the three most recently added products
curl -X POST   https://{store_name}.myshopify.com/admin/api/2025-10/graphql.json \
  -H 'Content-Type: application/json' \
  -H 'X-Shopify-Access-Token: {access_token}' \
  -d '{
  "query": "{
    products(first: 3) {
      edges {
        node {
          id
          title
        }
      }
    }
  }"
}'
```

***

## Rate limits

The GraphQL Admin API is rate-limited using calculated query costs, measured in cost points. Each field returned by a query costs a set number of points. The total cost of a query is the maximum of possible fields selected, so more complex queries cost more to run.

Learn more about [rate limits](https://shopify.dev/api/usage/limits#graphql-admin-api-rate-limits).

{}

## Request

```graphql
{
  products(first: 1) {
    edges {
      node {
        title
      }
    }
  }
}
```

{}

## Response

```json
{
  "data": {
    "products": {
      "edges": [
        {
          "node": {
            "title": "Hiking backpack"
          }
        }
      ]
    }
  },
  "extensions": {
    "cost": {
      "requestedQueryCost": 3,
      "actualQueryCost": 3,
      "throttleStatus": {
        "maximumAvailable": 1000.0,
        "currentlyAvailable": 997,
        "restoreRate": 50.0
      }
    }
  }
}
```

***

## Status and error codes

All API queries return HTTP status codes that contain more information about the response.

### 200 OK

GraphQL HTTP status codes are different from REST API status codes. Most importantly, the GraphQL API can return a `200 OK` response code in cases that would typically produce 4xx or 5xx errors in REST.

### Error handling

The response for the errors object contains additional detail to help you debug your operation.

The response for mutations contains additional detail to help debug your query. To access this, you must request `userErrors`.

#### Properties

* errorsarray

A list of all errors returned

* errors\[n].​messagestring

Contains details about the error(s).

* errors\[n].​extensionsobject

Provides more information about the error(s) including properties and metadata.

* errors\[n].​extensions.​codestring

Shows error codes common to Shopify. Additional error codes may also be shown.

* THROTTLED

The client has exceeded the [rate limit](#rate-limits). Similar to 429 Too Many Requests.

* ACCESS\_​DENIED

The client doesn’t have correct [authentication](#authentication) credentials. Similar to 401 Unauthorized.

* SHOP\_​INACTIVE

The shop is not active. This can happen when stores repeatedly exceed API rate limits or due to fraud risk.

* INTERNAL\_​SERVER\_​ERROR

Shopify experienced an internal error while processing the request. This error is returned instead of 500 Internal Server Error in most circumstances.

***

### 4xx and 5xx status codes

The 4xx and 5xx errors occur infrequently. They are often related to network communications, your account, or an issue with Shopify’s services.

Many errors that would typically return a 4xx or 5xx status code, return an HTTP 200 errors response instead. Refer to the [200 OK section](#200-ok) above for details.

{}

## Sample 200 error responses

```json
{
"errors": [
  {
    "message": "Query cost is 2003, which exceeds the single query max cost limit (1000).


See https://shopify.dev/concepts/about-apis/rate-limits for more information on how the
cost of a query is calculated.


To query larger amounts of data with fewer limits, bulk operations should be used instead.
See https://shopify.dev/tutorials/perform-bulk-operations-with-admin-api for usage details.
",
    "extensions": {
      "code": "MAX_COST_EXCEEDED",
      "cost": 2003,
      "maxCost": 1000,
      "documentation": "https://shopify.dev/api/usage/limits#rate-limits"
    }
  }
]
}
```

```json
{
"errors": [
  {
    "message": "Internal error. Looks like something went wrong on our end.
Request ID: 1b355a21-7117-44c5-8d8b-8948082f40a8 (include this in support requests).",
    "extensions": {
      "code": "INTERNAL_SERVER_ERROR",
      "requestId": "1b355a21-7117-44c5-8d8b-8948082f40a8"
    }
  }
]
}
```

##### Throttled

```
{
"errors": [
  {
    "message": "Query cost is 2003, which exceeds the single query max cost limit (1000).

See https://shopify.dev/concepts/about-apis/rate-limits for more information on how the
cost of a query is calculated.

To query larger amounts of data with fewer limits, bulk operations should be used instead.
See https://shopify.dev/tutorials/perform-bulk-operations-with-admin-api for usage details.
",
    "extensions": {
      "code": "MAX_COST_EXCEEDED",
      "cost": 2003,
      "maxCost": 1000,
      "documentation": "https://shopify.dev/api/usage/limits#rate-limits"
    }
  }
]
}
```

##### Internal

```
{
"errors": [
  {
    "message": "Internal error. Looks like something went wrong on our end.
Request ID: 1b355a21-7117-44c5-8d8b-8948082f40a8 (include this in support requests).",
    "extensions": {
      "code": "INTERNAL_SERVER_ERROR",
      "requestId": "1b355a21-7117-44c5-8d8b-8948082f40a8"
    }
  }
]
}
```

### 4xx and 5xx status codes

The 4xx and 5xx errors occur infrequently. They are often related to network communications, your account, or an issue with Shopify’s services.

Many errors that would typically return a 4xx or 5xx status code, return an HTTP 200 errors response instead. Refer to the [200 OK section](#200-ok) above for details.

***

#### 400 Bad Request

The server will not process the request.

***

#### 402 Payment Required

The shop is frozen. The shop owner will need to pay the outstanding balance to [unfreeze](https://help.shopify.com/en/manual/your-account/pause-close-store#unfreeze-your-shopify-store) the shop.

***

#### 403 Forbidden

The shop is forbidden. Returned if the store has been marked as fraudulent.

***

#### 404 Not Found

The resource isn’t available. This is often caused by querying for something that’s been deleted.

***

#### 423 Locked

The shop isn’t available. This can happen when stores repeatedly exceed API rate limits or due to fraud risk.

***

#### 5xx Errors

An internal error occurred in Shopify. Check out the [Shopify status page](https://www.shopifystatus.com) for more information.

***

Info

Didn’t find the status code you’re looking for? View the complete list of [API status response and error codes](https://shopify.dev/api/usage/response-codes).

{}

## Sample error codes

HTTP/1.1 400 Bad Request

{

"errors": {

"query": "Required parameter missing or invalid"

}

}

HTTP/1.1 402 Payment Required

{

"errors": "This shop's plan does not have access to this feature"

}

HTTP/1.1 403 Access Denied

{

"errors": "User does not have access"

}

HTTP/1.1 404 Not Found

{

"errors": "Not Found"

}

HTTP/1.1 423 Locked

{

"errors": "This shop is unavailable"

}

HTTP/1.1 500 Internal Server Error

{

"errors": "An unexpected error occurred"

}

##### 400

```
HTTP/1.1 400 Bad Request
{
  "errors": {
    "query": "Required parameter missing or invalid"
  }
}
```

##### 402

```
HTTP/1.1 402 Payment Required
{
  "errors": "This shop's plan does not have access to this feature"
}
```

##### 403

```
HTTP/1.1 403 Access Denied
{
  "errors": "User does not have access"
}
```

##### 404

```
HTTP/1.1 404 Not Found
{
  "errors": "Not Found"
}
```

##### 423

```
HTTP/1.1 423 Locked
{
  "errors": "This shop is unavailable"
}
```

##### 500

```
HTTP/1.1 500 Internal Server Error
{
  "errors": "An unexpected error occurred"
}
```

***