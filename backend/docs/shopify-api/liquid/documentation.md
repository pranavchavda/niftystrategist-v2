---
title: Liquid reference
description: >-
  The Liquid reference documents the Liquid tags, filters, and objects that you
  can use to build Shopify themes.
api_name: liquid
source_url:
  html: 'https://shopify.dev/docs/api/liquid'
  md: 'https://shopify.dev/docs/api/liquid.md'
---

# Liquid reference

Liquid is a template language created by Shopify. It's available as an [open source project](https://shopify.github.io/liquid/) on GitHub, and is used by many different software projects and companies.

This reference documents the Liquid tags, filters, and objects that you can use to build [Shopify Themes](https://shopify.dev/themes).

## What is a template language?

A template language allows you to create a single template to host static content, and dynamically insert information depending on where the template is rendered. For example, you can create a product template that hosts all of your standard product attributes, such as the product image, title, and price. That template can then dynamically render those attributes with the appropriate content, depending on the current product being viewed.

***

## Variations of Liquid

The variation of Liquid in this reference extends the open-source version of Liquid for use with [Shopify themes](https://shopify.dev/themes). It includes tags, filters, and objects that can be used to render objects specific to Shopify stores and storefront functionality.

Shopify also uses slightly different versions of Liquid to render dynamic content for the following features. These variations aren’t included in this reference.

[Notification templates](https://help.shopify.com/en/manual/orders/notifications/email-variables)

[Shopify Flow](https://help.shopify.com/en/manual/shopify-flow/reference/variables#liquid-variables)

[Order printer templates](https://help.shopify.com/en/manual/fulfillment/managing-orders/printing-orders/shopify-order-printer/liquid-variables-and-filters-reference)

[Packing slip templates](https://help.shopify.com/en/manual/orders/packing-slips-variable-list)

***

## Liquid basics

Liquid is used to dynamically output objects and their properties. You can further modify that output by creating logic with tags, or directly altering it with a filter. Objects and object properties are output using one of six basic data types. Liquid also includes basic logical and comparison operators for use with tags.

[Navigate to - Basics](https://shopify.dev/docs/api/liquid/basics)

## Code

```liquid
<title>
  {{ page_title }}
</title>
{% if page_description -%}
  <meta name="description" content="{{ page_description | truncate: 150 }}">
{%- endif %}
```

## Output

```html
<title>
  Health potion
</title>
<meta name="description" content="Are you low on health? Well we've got the potion just for you! Just need a top up? Almost dead? In between? No need to worry because we have a ...">
```

***

## Defining logic with tags

Liquid tags are used to define logic that tells templates what to do.

Tags are wrapped with curly brace percentage delimiters `{% %}`. The text within the delimiters is an instruction, not content to render.

In the example to the right, the `if` tag defines the condition to be met. If `product.available` returns `true`, then the price is displayed. Otherwise, the “sold out” message is shown.

`{% %}`

To nest multiple tags inside one set of delimiters, use the [`liquid`](https://shopify.dev/docs/api/liquid/tags/liquid) tag.

```liquid
{% if product.available %}
  Price: $99.99
{% else %}
  Sorry, this product is sold out.
{% endif %}
```

```json
{
  "product": {
    "available": true
  }
}
```

##### Code

```
{% if product.available %}
  Price: $99.99
{% else %}
  Sorry, this product is sold out.
{% endif %}
```

##### Data

```
{
  "product": {
    "available": true
  }
}
```

## Output

```html
Price: $99.99
```

### Tags with parameters

Some tags accept parameters: either required or optional. For example, the `for` tag takes an optional `limit` parameter to stop the loop at a specific index.

## Code

```liquid
{% assign numbers = '1,2,3,4,5' | split: ',' %}


{% for item in numbers limit:2 -%}
  {{ item }}
{%- endfor %}
```

## Output

```html
1
2
```

***

## Modifying output with filters

Liquid filters modify the output of variables and objects.

To filter the output of a tag, use the pipe character `|`, followed by the filter. In this example, `product` is the object, `title` is its property, and `upcase` is the filter.

```liquid
{% # product.title -> Health potion %}


{{ product.title | upcase }}
```

```json
{
  "product": {
    "title": "Health potion"
  }
}
```

##### Code

```
{% # product.title -> Health potion %}

{{ product.title | upcase }}
```

##### Data

```
{
  "product": {
    "title": "Health potion"
  }
}
```

## Output

```html
HEALTH POTION
```

### Filters with parameters

Many filters accept parameters that adjust their output. Some parameters are required, others are optional.

```liquid
{% # product.title -> Health potion %}


{{ product.title | remove: 'Health' }}
```

```json
{
  "product": {
    "title": "Health potion"
  }
}
```

##### Code

```
{% # product.title -> Health potion %}

{{ product.title | remove: 'Health' }}
```

##### Data

```
{
  "product": {
    "title": "Health potion"
  }
}
```

## Output

```html
potion
```

### Using multiple filters

Multiple filters can be used on one output. They're applied from left to right.

```liquid
{% # product.title -> Health potion %}


{{ product.title | upcase | remove: 'HEALTH' }}
```

```json
{
  "product": {
    "title": "Health potion"
  }
}
```

##### Code

```
{% # product.title -> Health potion %}

{{ product.title | upcase | remove: 'HEALTH' }}
```

##### Data

```
{
  "product": {
    "title": "Health potion"
  }
}
```

## Output

```html
POTION
```

***

## Referencing objects

Liquid objects represent variables that you can use to build your theme. Object types include, but aren't limited to:

* Store resources, such as a collection or product and its properties
* Standard content that is used to power Shopify themes, such as `content_for_header`
* Functional elements that can be used to build interactivity, such as `paginate` and `search`

Objects might represent a single data point, or contain multiple properties. Some products might represent a related object, such as a product in a collection.

`{{ }}`

Double curly brace delimiters denote an output.

### Usage

To output an object, wrap it in curly brace delimiters `{{ }}`.

To output an object's property, use dot notation. This example outputs the `product` object's `title` property.

```liquid
{{ product.title }}
```

```json
{
  "product": {
    "title": "Health potion"
  }
}
```

##### Code

```
{{ product.title }}
```

##### Data

```
{
  "product": {
    "title": "Health potion"
  }
}
```

## Output

```html
Health potion
```

### Object access

Objects can be accessed in three ways:

* **Globally**: Available in any Liquid file, excluding [checkout.liquid](https://shopify.dev/themes/architecture/layouts/checkout-liquid) and [Liquid asset files](https://shopify.dev/themes/architecture#assets)
* **In templates**: Available in specific templates and their sections or blocks. For example, the [`product`](https://shopify.dev/docs/api/liquid/objects/product) object in a [product template](https://shopify.dev/themes/architecture/templates/product)
* **Through parent objects**: Returned as properties of other objects. For example, [`article`](https://shopify.dev/docs/api/liquid/objects/article) objects through [`articles`](https://shopify.dev/docs/api/liquid/objects/articles) or [`blog`](https://shopify.dev/docs/api/liquid/objects/blog)

Check each object's documentation to see how it can be accessed.

### Creating variables

To create your own variables, use variable tags like [`assign`](https://shopify.dev/docs/api/liquid/tags/assign) or [`capture`](https://shopify.dev/docs/api/liquid/tags/capture). Syntactically, Liquid treats variables the same as objects.

## Code

```liquid
{% assign my_variable = 'My custom string.' %}
{{ my_variable }}
```

## Output

```html
My custom string.
```

***

## Resources & tools

[Liquid Cheat Sheet\
\
](https://www.shopify.com/partners/shopify-cheat-sheet)

[A simple reference guide to the Liquid language.](https://www.shopify.com/partners/shopify-cheat-sheet)

[Theme Check\
\
](https://shopify.dev/themes/tools/theme-check)

[Command line-based linter for themes. Also comes as an official Visual Studio Code extension.](https://shopify.dev/themes/tools/theme-check)

[Shopify CLI for Themes\
\
](https://shopify.dev/themes/tools/cli)

[A powerful command-line tool for building Shopify themes, and exploring Liquid code in a REPL interface.](https://shopify.dev/themes/tools/cli)

[Open source liquid\
\
](https://github.com/Shopify/liquid)

[Liquid is an open source project on GitHub.](https://github.com/Shopify/liquid)

***