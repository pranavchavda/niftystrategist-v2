---
title: Storefront API reference
description: The Storefront API provides commerce primitives to build custom, scalable, and performant shopping experiences. Learn how to get started using efficient GraphQL queries.
api_version: 2025-10
api_name: storefront
source_url:
  html: https://shopify.dev/docs/api/storefront/latest
  md: https://shopify.dev/docs/api/storefront/latest.md
---

# GraphQL Storefront API

Create unique customer experiences with the Storefront API on any platform, including the web, apps, and games. The API offers a full range of commerce options making it possible for customers to view [products](https://shopify.dev/custom-storefronts/products-collections/getting-started) and [collections](https://shopify.dev/custom-storefronts/products-collections/filter-products), add products to a [cart](https://shopify.dev/custom-storefronts/cart/manage), and [check out](https://shopify.dev/custom-storefronts/checkout).

Explore [Hydrogen](https://shopify.dev/custom-storefronts/hydrogen), Shopify’s official React-based framework for building headless commerce at global scale.

## Development frameworks and SDKs

Use Shopify’s officially supported libraries to build fast, reliable apps with the programming languages and frameworks you already know.

cURL

Use the [curl utility](https://curl.se/) to make API queries directly from the command line.

Hydrogen

A React-based framework for building custom storefronts on Shopify, Hydrogen has everything you need to build fast, and deliver personalized shopping experiences.

* [Docs](https://github.com/Shopify/hydrogen#readme)
* [npm package](https://www.npmjs.com/package/@shopify/hydrogen)
* [GitHub repo](https://github.com/Shopify/hydrogen)

Storefront API Client

The official lightweight client for any Javascript project interfacing with Storefront API and our recommended client for building custom storefronts without Hydrogen.

* [Docs](https://github.com/Shopify/shopify-app-js/tree/main/packages/api-clients/storefront-api-client#readme)
* [npm package](https://www.npmjs.com/package/@shopify/storefront-api-client)
* [GitHub repo](https://github.com/Shopify/shopify-app-js/tree/main/packages/api-clients/storefront-api-client)

React Router Apps

The official package for React Router apps.

* [Docs](https://shopify.dev/docs/api/shopify-app-react-router)
* [npm package](https://www.npmjs.com/package/@shopify/shopify-app-react-router)
* [GitHub repo](https://github.com/Shopify/shopify-app-template-react-router#readme)

Node.js

The official client library for Node.js applications, with full TypeScript support. It has no framework dependencies, so it can be used by any Node.js app.

* [Docs](https://github.com/Shopify/shopify-app-js/tree/main/packages/apps/shopify-api#readme)
* [npm package](https://www.npmjs.com/package/@shopify/shopify-api)
* [GitHub repo](https://github.com/Shopify/shopify-app-js/tree/main/packages/apps/shopify-api)

Shopify API (Apps)

The full suite library for TypeScript/JavaScript Shopify apps to access the GraphQL and REST Admin APIs and the Storefront API.

* [npm package](https://www.npmjs.com/package/@shopify/shopify-api)
* [GitHub repo](https://github.com/Shopify/shopify-app-js/tree/main/packages/apps/shopify-api)

Ruby

The official client library for Ruby applications. It has no framework dependencies, so it can be used by any Ruby app. This API applies a rate limit based on the IP address making the request, which will be your server’s address for all requests made by the library. Learn more about [rate limits](https://shopify.dev/api/usage/limits#rate-limits).

* [Docs](https://shopify.github.io/shopify-api-ruby/)
* [Ruby gem](https://rubygems.org/gems/shopify_api)
* [GitHub repo](https://github.com/Shopify/shopify-api-ruby)

Android

The official client library for Android apps.

* [Docs](https://github.com/Shopify/mobile-buy-sdk-android#readme)
* [GitHub repo](https://github.com/Shopify/mobile-buy-sdk-android)

iOS

The official client library for iOS applications.

* [Docs](https://github.com/Shopify/mobile-buy-sdk-ios#readme)
* [GitHub repo](https://github.com/Shopify/mobile-buy-sdk-ios)

Other

Other libraries are available in addition to the ones listed here. Check the list of [developer tools for custom storefronts](https://shopify.dev/custom-storefronts/tools).

```js
npm init @shopify/hydrogen
// or
npx @shopify/create-hydrogen
// or
pnpm create @shopify/create-hydrogen
// or
yarn create @shopify/hydrogen
```

```ts
npm install --save @shopify/storefront-api-client
// or
yarn add @shopify/storefront-api-client
```

```ts
npm install --save @shopify/shopify-app-react-router
// or
yarn add @shopify/shopify-app-react-router
```

```js
npm install --save @shopify/shopify-api
// or
yarn add @shopify/shopify-api
```

```ruby
bundle add shopify_api
```

##### Shopify Hydrogen storefront creation

```
npm init @shopify/hydrogen
// or
npx @shopify/create-hydrogen
// or
pnpm create @shopify/create-hydrogen
// or
yarn create @shopify/hydrogen
```

##### Storefront API client installation

```
npm install --save @shopify/storefront-api-client
// or
yarn add @shopify/storefront-api-client
```

##### Shopify app React Router package installation

```
npm install --save @shopify/shopify-app-react-router
// or
yarn add @shopify/shopify-app-react-router
```

##### Shopify API installation

```
npm install --save @shopify/shopify-api
// or
yarn add @shopify/shopify-api
```

##### Shopify Ruby library installation

```
bundle add shopify_api
```

***

## Authentication

The Storefront API supports both tokenless access and token-based authentication.

### Tokenless access

Tokenless access allows API queries without an access token providing access to essential features such as:

* Products and Collections
* Selling Plans
* Search
* Pages, Blogs, and Articles
* Cart (read/write)

Tokenless access has a query complexity limit of 1,000. Query complexity is calculated based on the cost of each field in the query. For more information, see the [Cost calculation](#rate-limits) section.

### Token-based authentication

For access to all Storefront API features, an access token is required. The following features require token-based authentication:

* Product Tags
* Metaobjects and Metafields
* Menu (Online Store navigation)
* Customers

The Storefront API has the following types of token-based access:

* **Public access**: Used to query the API from a browser or mobile app.
* **Private access**: Used to query the API from a server or other private context, like a Hydrogen backend.

Learn more about [access tokens for the Storefront API](https://shopify.dev/api/usage/authentication#access-tokens-for-the-storefront-api).

```bash
curl -X POST \
  https://{shop}.myshopify.com/api/2025-10/graphql.json \
  -H 'Content-Type: application/json' \
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

```bash
curl -X POST \
  https://{shop}.myshopify.com/api/2025-10/graphql.json \
  -H 'Content-Type: application/json' \
  -H 'X-Shopify-Storefront-Access-Token: {storefront-access-token}' \
  -d '{
    "query": "{your_query}"
  }'
```

```js
const storefront = createStorefrontClient({
publicStorefrontToken: env.PUBLIC_STOREFRONT_API_TOKEN,
storeDomain: `https://\${env.PUBLIC_STORE_DOMAIN}\`,
storefrontApiVersion: env.PUBLIC_STOREFRONT_API_VERSION || '2023-01',
});
```

```ts
import {createStorefrontApiClient} from '@shopify/storefront-api-client';


const client = createStorefrontApiClient({
  storeDomain: 'http://your-shop-name.myshopify.com',
  apiVersion: '2025-10',
  publicAccessToken: <your-storefront-public-access-token>,
});
```

```ts
import { authenticate } from "../shopify.server";


// Use private access token on requests that don't come from Shopify
const { storefront } = await unauthenticated.storefront(shop);
// OR
// Use private access token for app proxy requests
const { storefront } = await authenticate.public.appProxy(request);
```

```js
const adminApiClient = new shopify.clients.Rest({session});
const storefrontTokenResponse = await adminApiClient.post({
  path: 'storefront_access_tokens',
  type: DataType.JSON,
  data: {
    storefront_access_token: {
      title: 'This is my test access token',
    },
  },
});


const storefrontAccessToken =
  storefrontTokenResponse.body['storefront_access_token']['access_token'];
```

```ruby

# Create a REST client from your offline session
client = ShopifyAPI::Clients::Rest::Admin.new(
  session: session
)

# Create a new access token
storefront_token_response = client.post(
  path: 'storefront_access_tokens',
  body: {
    storefront_access_token: {
      title: "This is my test access token",
    }
  }
)


storefront_access_token = storefront_token_response.body['storefront_access_token']['access_token']
```

##### Tokenless (cURL)

```
curl -X POST \
  https://{shop}.myshopify.com/api/2025-10/graphql.json \
  -H 'Content-Type: application/json' \
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

##### Token-based (cURL)

```
curl -X POST \
  https://{shop}.myshopify.com/api/2025-10/graphql.json \
  -H 'Content-Type: application/json' \
  -H 'X-Shopify-Storefront-Access-Token: {storefront-access-token}' \
  -d '{
    "query": "{your_query}"
  }'
```

##### Hydrogen

```
const storefront = createStorefrontClient({
publicStorefrontToken: env.PUBLIC_STOREFRONT_API_TOKEN,
storeDomain: `https://\${env.PUBLIC_STORE_DOMAIN}\`,
storefrontApiVersion: env.PUBLIC_STOREFRONT_API_VERSION || '2023-01',
});
```

##### Storefront API Client

```
import {createStorefrontApiClient} from '@shopify/storefront-api-client';

const client = createStorefrontApiClient({
  storeDomain: 'http://your-shop-name.myshopify.com',
  apiVersion: '2025-10',
  publicAccessToken: <your-storefront-public-access-token>,
});
```

##### React Router

```
import { authenticate } from "../shopify.server";

// Use private access token on requests that don't come from Shopify
const { storefront } = await unauthenticated.storefront(shop);
// OR
// Use private access token for app proxy requests
const { storefront } = await authenticate.public.appProxy(request);
```

##### Shopify API

```
const adminApiClient = new shopify.clients.Rest({session});
const storefrontTokenResponse = await adminApiClient.post({
  path: 'storefront_access_tokens',
  type: DataType.JSON,
  data: {
    storefront_access_token: {
      title: 'This is my test access token',
    },
  },
});

const storefrontAccessToken =
  storefrontTokenResponse.body['storefront_access_token']['access_token'];
```

##### Ruby

```

# Create a REST client from your offline session
client = ShopifyAPI::Clients::Rest::Admin.new(
  session: session
)

# Create a new access token
storefront_token_response = client.post(
  path: 'storefront_access_tokens',
  body: {
    storefront_access_token: {
      title: "This is my test access token",
    }
  }
)

storefront_access_token = storefront_token_response.body['storefront_access_token']['access_token']
```

***

## Endpoints and queries

The Storefront API is available only in GraphQL. There's no REST API for storefronts.

All Storefront API queries are made on a single GraphQL endpoint, which only accepts `POST` requests:

`https://{store_name}.myshopify.com/api/2025-10/graphql.json`

### Versioning

The Storefront API is [versioned](https://shopify.dev/api/usage/versioning), with new releases four times a year. To keep your app stable, make sure that you specify a supported version in the URL.

### Graphi​QL explorer

Explore and learn Shopify's Storefront API using the [GraphiQL explorer](https://shopify.dev/custom-storefronts/tools/graphiql-storefront-api). To build queries and mutations with shop data, install [Shopify's GraphiQL app](https://shopify-graphiql-app.shopifycloud.com/).

### Usage limitations

* Shopify Plus [bot protection](https://help.shopify.com/en/manual/checkout-settings/bot-protection) is only available for the [Cart](https://shopify.dev/custom-storefronts/cart/manage) object. It isn't available for the [Checkout](https://shopify.dev/custom-storefronts/checkout) object.
* You can't use Storefront API to duplicate existing Shopify functionality—be sure to check the API terms of service before you start.

POST

## https://{store\_name}.myshopify.com/api/2025-10/graphql.json

```bash

# Get the ID and title of the three most recently added products
curl -X POST \
  https://{store_name}.myshopify.com/api/2025-10/graphql.json \
  -H 'Content-Type: application/json' \
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

```bash

# Get the ID and title of the three most recently added products
curl -X POST \
  https://{store_name}.myshopify.com/api/2025-10/graphql.json \
  -H 'Content-Type: application/json' \
  -H 'X-Shopify-Storefront-Access-Token: {storefront_access_token}' \
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

```javascript
import {json} from '@shopify/remix-oxygen';


export async function loader({context}) {
  const PRODUCTS_QUERY = `#graphql
    query products {
      products(first: 3) {
        edges {
          node {
            id
            title
          }
        }
      }
    }
  `;
  const {products} = await context.storefront.query(PRODUCTS_QUERY);
  return json({products});
}
```

```ts
const productQuery = `
  query ProductQuery($handle: String) {
    product(handle: $handle) {
      id
      title
      handle
    }
  }
`;


const {data, errors, extensions} = await client.request(productQuery, {
  variables: {
    handle: 'sample-product',
  },
});
```

```ts
const { storefront } = await unauthenticated.storefront(
  'your-development-store.myshopify.com'
);


const response = await storefront.graphql(
  `#graphql
  query products {
    products(first: 3) {
      edges {
        node {
          id
          title
        }
      }
    }
  }`,
);


const data = await response.json();
```

```js
// Load the access token as per instructions above
const storefrontAccessToken = '<my token>';
// Shop from which we're fetching data
const shop = 'my-shop.myshopify.com';


// StorefrontClient takes in the shop url and the Storefront Access Token for that shop.
const storefrontClient = new shopify.clients.Storefront({
  domain: shop,
  storefrontAccessToken,
});


// Use client.query and pass your query as \`data\`
const products = await storefrontClient.query({
  data: `{
    products (first: 3) {
      edges {
        node {
          id
          title
        }
      }
    }
  }`,
});
```

```ruby

# Load the access token as per instructions above
store_front_access_token = '<my token>'

# Shop from which we're fetching data
shop = 'my-shop.myshopify.com'

# The Storefront client takes in the shop url and the Storefront Access Token for that shop.
storefront_client = ShopifyAPI::Clients::Graphql::Storefront.new(
  shop,
  storefront_access_token
)

# Call query and pass your query as `data`
my_query = <<~QUERY
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
QUERY
products = storefront_client.query(query: my_query)
```

##### Tokenless request

```

# Get the ID and title of the three most recently added products
curl -X POST \
  https://{store_name}.myshopify.com/api/2025-10/graphql.json \
  -H 'Content-Type: application/json' \
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

##### Token-based request

```

# Get the ID and title of the three most recently added products
curl -X POST \
  https://{store_name}.myshopify.com/api/2025-10/graphql.json \
  -H 'Content-Type: application/json' \
  -H 'X-Shopify-Storefront-Access-Token: {storefront_access_token}' \
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

##### Hydrogen

```
import {json} from '@shopify/remix-oxygen';

export async function loader({context}) {
  const PRODUCTS_QUERY = `#graphql
    query products {
      products(first: 3) {
        edges {
          node {
            id
            title
          }
        }
      }
    }
  `;
  const {products} = await context.storefront.query(PRODUCTS_QUERY);
  return json({products});
}
```

##### Storefront API Client

```
const productQuery = `
  query ProductQuery($handle: String) {
    product(handle: $handle) {
      id
      title
      handle
    }
  }
`;

const {data, errors, extensions} = await client.request(productQuery, {
  variables: {
    handle: 'sample-product',
  },
});
```

##### React Router

```
const { storefront } = await unauthenticated.storefront(
  'your-development-store.myshopify.com'
);

const response = await storefront.graphql(
  `#graphql
  query products {
    products(first: 3) {
      edges {
        node {
          id
          title
        }
      }
    }
  }`,
);

const data = await response.json();
```

##### Shopify API

```
// Load the access token as per instructions above
const storefrontAccessToken = '<my token>';
// Shop from which we're fetching data
const shop = 'my-shop.myshopify.com';

// StorefrontClient takes in the shop url and the Storefront Access Token for that shop.
const storefrontClient = new shopify.clients.Storefront({
  domain: shop,
  storefrontAccessToken,
});

// Use client.query and pass your query as \`data\`
const products = await storefrontClient.query({
  data: `{
    products (first: 3) {
      edges {
        node {
          id
          title
        }
      }
    }
  }`,
});
```

##### Ruby

```

# Load the access token as per instructions above
store_front_access_token = '<my token>'

# Shop from which we're fetching data
shop = 'my-shop.myshopify.com'

# The Storefront client takes in the shop url and the Storefront Access Token for that shop.
storefront_client = ShopifyAPI::Clients::Graphql::Storefront.new(
  shop,
  storefront_access_token
)

# Call query and pass your query as `data`
my_query = <<~QUERY
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
QUERY
products = storefront_client.query(query: my_query)
```

***

## Directives

A directive provides a way for apps to describe additional options to the GraphQL executor. It lets GraphQL change the result of the query or mutation based on the additional information provided by the directive.

### Storefront Directives

@inContext (Country Code)

In the Storefront API, the `@inContext` directive takes an optional [country code argument](https://shopify.dev/api/storefront/2025-10/enums/countrycode) and applies this to the query or mutation.

This example shows how to retrieve a list of available countries and their corresponding currencies for a shop that's located in France `@inContext(country: FR)`.

* [Examples for localized pricing](https://shopify.dev/api/examples/international-pricing)
* [GQL directives spec](https://graphql.org/learn/queries/#directives)

@inContext (Language)

In the Storefront API, beyond version 2022-04, the `@inContext` directive can contextualize any query to one of a shop's available languages with an optional [language code argument](https://shopify.dev/api/storefront/2025-10/enums/LanguageCode).

This example shows how to return a product's `title`, `description`, and `options` translated into Spanish `@inContext(language: ES)`.

* [Examples for supporting multiple languages](https://shopify.dev/api/examples/multiple-languages)
* [GQL directives spec](https://graphql.org/learn/queries/#directives)

@inContext (Buyer Identity)

In the Storefront API, beyond version 2024-04, the `@inContext` directive can contextualize any query to a logged in buyer of a shop with an optional [buyer argument](https://shopify.dev/api/storefront/2025-10/input-objects/BuyerInput).

This example shows how to return a product's price `amount` contextualized for a business customer buyer `@inContext(buyer: {customerAccessToken: 'token', companyLocationId: 'gid://shopify/CompanyLocation/1'})`.

* [Example for supporting a contextualized buyer identity](https://shopify.dev/custom-storefronts/headless/b2b#step-3-contextualize-storefront-api-requests)
* [GraphQL directives spec](https://graphql.org/learn/queries/#directives)

@inContext (Visitor Consent)

In the Storefront API, beyond version 2025-10, the `@inContext` directive can contextualize any query or mutation with visitor consent information using an optional `visitorConsent` argument.

This example shows how to create a cart with visitor consent preferences `@inContext(visitorConsent: {analytics: true, preferences: true, marketing: false, saleOfData: false})`.

The consent information is automatically encoded and included in the resulting [`checkoutUrl`](https://shopify.dev/docs/api/storefront/latest/objects/Cart#field-Cart.fields.checkoutUrl) to ensure privacy compliance throughout the checkout process. All consent fields are optional.

* [Examples for collecting and passing visitor consent with Checkout Kit](https://shopify.dev/docs/storefronts/mobile/checkout-kit/privacy-compliance)
* [GraphQL directives spec](https://graphql.org/learn/queries/#directives)

@defer

The `@defer` directive allows clients to prioritize part of a GraphQL query without having to make more requests to fetch the remaining information. It does this through streaming, where the first response contains the data that isn't deferred.

The directive accepts two optional arguments: `label` and `if`. The `label` is included in the fragment response if it's provided in the directive. When the `if` argument is `false`, the fragment isn't deferred.

This example shows how to return a product's `title` and `description` immediately, and then return the `descriptionHtml` and `options` after a short delay.

The `@defer` directive is available as a [developer preview](https://shopify.dev/docs/api/developer-previews#defer-directive-developer-preview) in `unstable`.

* [Examples for how to use `@defer`](https://shopify.dev/docs/custom-storefronts/building-with-the-storefront-api/defer)

## Operation

```graphql
query productDetails {
  productByHandle(handle: "baseball-t-shirt") {
    title
    description
    ... @defer(label: "Extra info") {
      descriptionHtml
      options {
        name
        values
      }
    }
  }
}
```

## Response

JSON

```json
--graphql
Content-Type: application/json
Content-Length: 158


{
  "data": {
    "productByHandle": {
      "title": "Baseball t-shirt",
      "description": "description":"3 strikes, you're... never out of style in this vintage-inspired tee."
    }
  },
  "hasNext": true
}


--graphql
Content-Type: application/json
Content-Length: 295


{
  "incremental": [{
    "path": ["productByHandle"],
    "label": "Extra info",
    "data": {
      "descriptionHtml": "<p>3 strikes, you're... never out of style in this vintage-inspired tee. </p>",
      "options": [
        {
          "name": "Size",
          "values": ["Small", "Medium", "Large"]
        },
        {
          "name": "Color",
          "values": ["White", "Red"]
        }
      ]
    }
  }],
  "hasNext": false
}


--graphql--
```

***

## Rate limits

The Storefront API is designed to support businesses of all sizes. The Storefront API will scale to support surges in buyer traffic or your largest flash sale. There are no rate limits applied on the number of requests that can be made to the API.

The Storefront API provides protection against malicious users, such as bots, from consuming a high level of capacity. If a request appears to be malicious, Shopify will respond with a `430 Shopify Security Rejection` [error code](https://shopify.dev/docs/api/usage/response-codes) to indicate potential security concerns. Ensure requests to the Storefront API include the correct [Buyer IP header](https://shopify.dev/docs/api/usage/authentication#optional-ip-header).

[Learn more about rate limits](https://shopify.dev/docs/api/usage/limits#rate-limits).

### Query complexity limit for tokenless access

Tokenless access has a query complexity limit of 1,000. This limit is calculated based on the cost of each field in the query in the same way as the GraphQL Admin API. For more information on how query costs are calculated, see the [Cost calculation](https://shopify.dev/docs/api/usage/limits#rate-limits#cost-calculation) section in the API rate limits documentation.

When using tokenless access, query complexity that exceeds 1,000 will result in an error.

{}

## Query complexity exceeded error response

```json
{
  "errors": [
    {
      "message": "Complexity exceeded",
      "extensions": {
        "code": "MAX_COMPLEXITY_EXCEEDED",
        "cost": 1250,
        "maxCost": 1000
      }
    }
  ]
}
```

{}

## Response

```json
{
  "errors": [
    {
      "message": "Internal error. Looks like something went wrong on our end.
        Request ID: 1b355a21-7117-44c5-8d8b-8948082f40a8 (include this in support requests).",
      "extensions": {
        "code": "INTERNAL_SERVER_ERROR"
      }
    }
  ]
}
```

***

## Status and error codes

All API queries return HTTP status codes that contain more information about the response.

### 200 OK

The Storefront API can return a `200 OK` response code in cases that would typically produce 4xx errors in REST.

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

* extensions.​codestring

Shows error codes common to Shopify. Additional error codes may also be shown.

* ACCESS\_​DENIED

The client doesn’t have correct [authentication](#authentication) credentials. Similar to 401 Unauthorized.

* SHOP\_​INACTIVE

The shop is not active. This can happen when stores repeatedly exceed API rate limits or due to fraud risk.

* INTERNAL\_​SERVER\_​ERROR

Shopify experienced an internal error while processing the request. This error is returned instead of 500 Internal Server Error in most circumstances.

***

{}

## Sample 200 error responses

```json
{
  "errors": [
    {
      "message": "Throttled",
      "extensions": {
        "code": "THROTTLED"
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
        "code": "INTERNAL_SERVER_ERROR"
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
      "message": "Throttled",
      "extensions": {
        "code": "THROTTLED"
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
        "code": "INTERNAL_SERVER_ERROR"
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

HTTP/1.1 403 Forbidden

{

"errors": "Unavailable Shop"

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
HTTP/1.1 403 Forbidden
{
  "errors": "Unavailable Shop"
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

## Resources

[Get started\
\
](https://shopify.dev/docs/storefronts/headless/building-with-the-storefront-api)

[Learn more about how the Storefront API works and how to get started with it.](https://shopify.dev/docs/storefronts/headless/building-with-the-storefront-api)

[Storefront Learning Kit\
\
](https://github.com/Shopify/storefront-api-learning-kit)

[Explore a downloadable package of sample GraphQL queries for the Storefront API.](https://github.com/Shopify/storefront-api-learning-kit)

[Developer changelog\
\
](https://shopify.dev/changelog)

[Read about the changes currently introduced in the latest version of the Storefront API.](https://shopify.dev/changelog)

***