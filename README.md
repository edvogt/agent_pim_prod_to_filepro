# Pimcore to Shopify Product Sync Tool

Automated synchronization tool that imports product data from Pimcore PIM system to Shopify e-commerce platform.

## Overview

This application fetches product data from Pimcore via GraphQL API, transforms and validates the data using Pydantic models, and synchronizes products to Shopify with support for variants, images, and metafields.

---

## Architecture Components

### 1. **Main Entry Point** (`0_main.py`)
- Command-line interface with argument parsing
- Environment variable loading and validation
- Logging configuration (verbose/compact modes)
- Orchestrates initialization of all components

### 2. **Pimcore Client** (`pimcore_client.py`)
- GraphQL API communication with Pimcore
- Product fetching with PartPrefix filtering
- Asset retrieval (images)
- Schema introspection and connectivity testing

### 3. **Data Models** (`models.py`)
- Pydantic validation models
- Data transformation (HTML sanitization, title generation)
- Price logic (web_price fallback to retail_price)
- Business rule implementation

### 4. **Shopify Client** (`shopify_client.py`)
- GraphQL and REST API communication with Shopify
- Product create/update operations
- Variant management (pricing, inventory, MPN metafields)
- Image upload handling
- Rate limiting and error recovery

### 5. **Sync Engine** (`sync_engine.py`)
- Main synchronization loop
- Coordinates data flow between components
- Progress tracking and output formatting
- Delay/throttle management

---

## Workflow Diagram (Block Diagram Representation)

### High-Level Flow

```
┌─────────────────┐
│  User Input     │
│  (CLI Args)     │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────┐
│  0_main.py                      │
│  - Parse Arguments              │
│  - Load Environment Variables   │
│  - Configure Logging            │
│  - Validate Configuration       │
└────────┬────────────────────────┘
         │
         ├─────────────────┐
         ▼                 ▼
┌─────────────────┐  ┌─────────────────┐
│ PimcoreClient   │  │ ShopifyClient   │
│ Initialization  │  │ Initialization  │
└────────┬────────┘  └────────┬────────┘
         │                    │
         └────────┬───────────┘
                  │
                  ▼
         ┌─────────────────┐
         │  SyncEngine     │
         │  Initialization │
         └────────┬────────┘
                  │
                  ▼
         ┌─────────────────┐
         │  Sync Loop      │
         └────────┬────────┘
                  │
                  │ Loop for each product
                  │
                  ▼
```

### Detailed Product Sync Flow

```
┌─────────────────────────────────────────────────────────────┐
│ STEP 1: Fetch Products from Pimcore                         │
│ ─────────────────────────────────────────────────────────── │
│  PimcoreClient.fetch_products(prefix, limit)                │
│  │                                                           │
│  ├─► GraphQL Query: getProdM06Listing(filter: PartPrefix)   │
│  ├─► Parse Response: Extract product nodes                  │
│  └─► Return: List[PimcoreProduct]                           │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ STEP 2: Data Transformation & Validation                    │
│ ─────────────────────────────────────────────────────────── │
│  PimcoreProduct Model (Pydantic)                            │
│  │                                                           │
│  ├─► Map Pimcore fields → Python attributes                │
│  ├─► Validate data types                                    │
│  ├─► Apply business rules:                                  │
│  │   • effective_web_price (fallback logic)                │
│  │   • selected_price (minimum price calculation)          │
│  │   • shopify_title (truncation to 255 chars)             │
│  │   • get_sanitized_html() (HTML cleaning)                │
│  └─► Return: Validated PimcoreProduct object               │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ STEP 3: Product Upsert (Create or Update)                   │
│ ─────────────────────────────────────────────────────────── │
│  ShopifyClient.upsert_product(product_data)                 │
│  │                                                           │
│  ├─► GraphQL Mutation: productCreate                        │
│  │   ├─► Input: title, descriptionHtml, vendor, handle     │
│  │   └─► Output: product { id }                            │
│  │                                                           │
│  ├─► If handle exists (error):                             │
│  │   ├─► Query: productByHandle                            │
│  │   └─► Mutation: productUpdate                           │
│  │                                                           │
│  └─► Return: product_gid (GraphQL ID)                      │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ STEP 4: Variant Sync                                        │
│ ─────────────────────────────────────────────────────────── │
│  ShopifyClient.sync_variant(product_gid, sku, price, ...)   │
│  │                                                           │
│  ├─► REST GET: /products/{id}/variants.json                │
│  ├─► Extract: variant_id from response                     │
│  │                                                           │
│  ├─► REST PUT: /variants/{id}.json                         │
│  │   ├─► Update: sku, price, barcode                       │
│  │   ├─► Set: inventory_management = null                  │
│  │   └─► Set: inventory_policy = "continue"                │
│  │                                                           │
│  └─► Delay: 1.5 seconds                                     │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ STEP 5: MPN Metafield Setup                                 │
│ ─────────────────────────────────────────────────────────── │
│  ShopifyClient.set_variant_metafield(...)                   │
│  │                                                           │
│  ├─► GraphQL Mutation: metafieldsSet                        │
│  │   ├─► Set: mm-google-shopping.mpn = vendor_part_number  │
│  │   └─► Set: custom.vendor_part = vendor_part_number      │
│  │                                                           │
│  └─► Verify: Metafields created successfully                │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ STEP 6: Image Upload (if available)                         │
│ ─────────────────────────────────────────────────────────── │
│  IF image_asset_id exists:                                  │
│  │                                                           │
│  ├─► PimcoreClient.get_asset_data(asset_id)                │
│  │   ├─► GraphQL Query: getAsset(id)                       │
│  │   ├─► Parse: base64 data                                │
│  │   └─► Return: image_bytes                               │
│  │                                                           │
│  ├─► ShopifyClient.upload_image(product_gid, image_bytes)  │
│  │   ├─► REST POST: /products/{id}/images.json             │
│  │   ├─► Payload: base64 encoded image attachment          │
│  │   └─► Verify: Image uploaded successfully               │
│  │                                                           │
│  └─► Delay: 1.5 seconds (after image)                      │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ STEP 7: Progress Output                                     │
│ ─────────────────────────────────────────────────────────── │
│  IF verbose mode:                                           │
│  │   Log: Detailed progress with timestamps                │
│  ELSE (compact mode):                                       │
│  │   Output: SKU,Status Image,Status Completed,Item#/Total │
│  │   Example: AJA-123,✓,✓,1/200                            │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ STEP 8: Throttle Delay                                      │
│ ─────────────────────────────────────────────────────────── │
│  Delay: 1.5 seconds (between products)                     │
└─────────────────────────────────────────────────────────────┘
                         │
                         ├─► Loop back to STEP 1 for next product
                         │
                         ▼
                  ┌──────────────┐
                  │ Sync Complete│
                  └──────────────┘
```

---

## Data Flow Diagram

### Input → Transformation → Output

```
PIMCORE (Source)
│
├─► GraphQL API Query
│   └─► Product Fields:
│       • id, sku, upc
│       • WebPrice, MAP, Retail
│       • BrandName, Model, VendorPartNumber
│       • Description_Short, Description_Medium
│       • Specifications_WYSIWYG
│       • ImagePrimary { id }
│
▼
┌────────────────────────────────────┐
│ DATA TRANSFORMATION LAYER          │
│ (models.py - Pydantic Models)      │
│                                    │
│ • Field mapping (alias)            │
│ • Type validation                  │
│ • Business logic:                  │
│   - effective_web_price            │
│   - selected_price (min of 3)      │
│   - shopify_title (255 char limit) │
│   - sanitized_html (h2→h3)         │
└────────────────────────────────────┘
│
▼
SHOPIFY (Destination)
│
├─► Product Creation/Update
│   └─► Fields:
│       • title (shopify_title)
│       • descriptionHtml (sanitized)
│       • vendor (brand_name)
│       • handle (sku-based)
│       • status (ACTIVE)
│
├─► Variant Update
│   └─► Fields:
│       • sku
│       • price (selected_price)
│       • barcode (upc)
│       • inventory_management (null)
│       • inventory_policy ("continue")
│
├─► Metafields
│   └─► Fields:
│       • mm-google-shopping.mpn
│       • custom.vendor_part
│
└─► Image Asset
    └─► Binary upload (base64)
```

---

## Component Interaction Sequence

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│   Main   │───►│ Pimcore  │───►│  Models  │───►│ Shopify  │
│  Entry   │    │  Client  │    │          │    │  Client  │
└──────────┘    └──────────┘    └──────────┘    └──────────┘
     │               │               │               │
     │ 1. Init       │               │               │
     ├──────────────►│               │               │
     │               │               │               │
     │               │ 2. Fetch      │               │
     │               ├──────────────►│               │
     │               │               │               │
     │               │ 3. Validate   │               │
     │               │◄──────────────┤               │
     │               │               │               │
     │ 4. Sync       │               │               │
     ├──────────────────────────────────────────────►│
     │               │               │               │
     │               │               │ 5. Transform  │
     │               │               ├──────────────►│
     │               │               │               │
     │               │               │ 6. Create     │
     │               │               │◄──────────────┤
     │               │               │               │
     │               │ 7. Get Image  │               │
     ├──────────────►│               │               │
     │               │               │               │
     │               │ 8. Upload     │               │
     ├──────────────────────────────────────────────►│
```

---

## Key Features

### 1. **Price Management**
- Selects minimum of: WebPrice, MAP, Retail (only prices > 0)
- Fallback: If WebPrice is null/zero, uses RetailPrice

### 2. **MPN Metafield Support**
- Sets both `mm-google-shopping.mpn` (Google Shopping)
- Sets `custom.vendor_part` (standard MPN)
- Both use VendorPartNumber from Pimcore

### 3. **Inventory Management**
- Inventory tracking disabled (`inventory_management: null`)
- Continue selling when out of stock enabled

### 4. **Output Modes**
- **Verbose Mode** (`--verbose`): Full detailed logging
- **Compact Mode** (default): CSV-style progress output

### 5. **Rate Limiting**
- 1.5 seconds delay after image upload
- 1.5 seconds delay between products
- Configurable via environment variables

---

## Usage

### Basic Sync
```bash
python 0_main.py --prefix "VIZ" --max 10
```

### Verbose Mode
```bash
python 0_main.py --prefix "VIZ" --max 10 --verbose
```

### Dry Run (Test)
```bash
python 0_main.py --prefix "VIZ" --max 5 --dry-run
```

### Test Modes
```bash
# Test if records exist
python 0_main.py --test-records-exist

# Inspect available fields
python 0_main.py --test-no-filter --max 3
```

---

## Configuration

### Environment Variables (`.env.export`)
```
PIMCORE_BASE_URL=http://pimcore.ear.net
PIMCORE_ENDPOINT_NAME=api_06
PIMCORE_API_KEY=your_api_key

SHOPIFY_DOMAIN_MYSHOPIFY=your-store.myshopify.com
SHOPIFY_ADMIN_TOKEN=your_admin_token
SHOPIFY_API_VERSION=2025-10

DELAY_BETWEEN_PRODUCTS=1.5  # Optional (default: 1.5)
DELAY_AFTER_IMAGE=1.5       # Optional (default: 1.5)
```

---

## Version

Current Version: **1.3.0**

### Recent Changes (v1.3.0)
- Added verbose mode with compact CSV output
- Implemented MPN metafield support (Google/MPN and custom.vendor_part)
- Added web_price fallback to retail_price when null/zero
- Reduced all delays to 1.5 seconds
- Disabled inventory tracking
- Improved error handling and logging

---

## Dependencies

See `requirements.txt`:
- `requests==2.32.3` - HTTP client
- `pydantic==2.10.4` - Data validation
- `python-dotenv==1.0.1` - Environment variables
- `tqdm==4.67.1` - Progress bars (optional)
