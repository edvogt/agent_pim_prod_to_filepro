# agent_pimcore_pull_from_filepro

Product data fetching tool that pulls product data from Pimcore PIM system (via FilePro integration) using GraphQL API.

## Overview

This application fetches product data from Pimcore (via FilePro integration) using GraphQL API, transforms and validates the data using Pydantic models, and displays product information with support for filtering by PartPrefix.

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

### 4. **Fetch Engine** (`sync_engine.py`)
- Main product fetching loop
- Coordinates data retrieval from Pimcore
- Progress tracking and output formatting
- Product data display (verbose and compact modes)

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
         │
         ▼
┌─────────────────┐
│ PimcoreClient   │
│ Initialization  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  FetchEngine    │
│  Initialization │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Fetch Loop     │
└────────┬────────┘
         │
         │ Loop for each product
         │
         ▼
```

### Detailed Product Fetch Flow

```
┌─────────────────────────────────────────────────────────────┐
│ STEP 1: Fetch Products from Pimcore                         │
│ ─────────────────────────────────────────────────────────── │
│  PimcoreClient.fetch_products(prefix, limit)                │
│  │                                                           │
│  ├─► GraphQL Query: getProdM07Listing(filter: PartPrefix)   │
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
│  │   • product_title (truncation to 255 chars)             │
│  │   • get_sanitized_html() (HTML cleaning)                │
│  └─► Return: Validated PimcoreProduct object               │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ STEP 3: Display Product Information                         │
│ ─────────────────────────────────────────────────────────── │
│  IF verbose mode:                                           │
│  │   Log: Detailed product info with all fields            │
│  │   • SKU, Brand, Model, Price, UPC                        │
│  │   • Vendor Part Number, Image Asset ID                   │
│  │   • Title, Description                                   │
│  ELSE (compact mode):                                       │
│  │   Output: SKU,Brand,Model,Price,Image Available,Item#/Total │
│  │   Example: AJA-123,Brand,Model,99.99,✓,1/200            │
└─────────────────────────────────────────────────────────────┘
                         │
                         ├─► Loop back to STEP 1 for next product
                         │
                         ▼
                  ┌──────────────┐
                  │ Fetch Complete│
                  └──────────────┘
```

---

## Data Flow Diagram

### Input → Transformation → Display

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
│   - product_title (255 char limit) │
│   - sanitized_html (h2→h3)         │
└────────────────────────────────────┘
│
▼
OUTPUT (Display)
│
├─► Verbose Mode
│   └─► Detailed Logging:
│       • SKU, Brand, Model
│       • Price, UPC, Vendor Part
│       • Image Asset ID
│       • Title, Description
│
└─► Compact Mode
    └─► CSV-style Output:
        • SKU,Brand,Model,Price,Image,Item#/Total
```

---

## Component Interaction Sequence

```
┌──────────┐    ┌──────────┐    ┌──────────┐
│   Main   │───►│ Pimcore  │───►│  Models  │
│  Entry   │    │  Client  │    │          │
└──────────┘    └──────────┘    └──────────┘
     │               │               │
     │ 1. Init       │               │
     ├──────────────►│               │
     │               │               │
     │               │ 2. Fetch      │
     │               ├──────────────►│
     │               │               │
     │               │ 3. Validate   │
     │               │◄──────────────┤
     │               │               │
     │ 4. Display    │               │
     ├──────────────────────────────►│
     │               │               │
     │               │ 5. Transform  │
     │               │               │
```

---

## Key Features

### 1. **Price Management**
- Selects minimum of: WebPrice, MAP, Retail (only prices > 0)
- Fallback: If WebPrice is null/zero, uses RetailPrice

### 2. **Data Validation**
- Pydantic models ensure data integrity
- Type validation and field mapping
- HTML sanitization and title generation

### 3. **Output Modes**
- **Verbose Mode** (`--verbose`): Full detailed product information
- **Compact Mode** (default): CSV-style output with key fields

### 4. **Product Filtering**
- Filter by PartPrefix for targeted product retrieval
- Configurable limit on number of products fetched

---

## Usage

### Basic Fetch
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
```

---

## Version

Current Version: **2.2.0**

### Recent Changes (v2.2.0)
- Pimcore-only: fetches product data and exports to TSV for legacy invoice systems
- Renamed `product_title` property for generated titles (Brand + Model + Description)
- Streamlined workflow with verbose and compact output modes

---

## Dependencies

See `requirements.txt`:
- `requests==2.32.3` - HTTP client
- `pydantic==2.10.4` - Data validation
- `python-dotenv==1.0.1` - Environment variables
- `tqdm==4.67.1` - Progress bars (optional)
