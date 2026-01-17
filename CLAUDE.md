# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Pimcore PIM data export tool that fetches product data from Pimcore (via FilePro integration) using GraphQL API and exports to tab-delimited TSV files for legacy invoice systems.

## Development Commands

```bash
# Setup
python -m venv venv && source venv/bin/activate && pip install -r requirements.txt

# Basic usage - exports TSV file
python 0_main.py --prefix "VIZ" --max 10

# Verbose mode (DEBUG logging)
python 0_main.py --prefix "EAR" --max 5 --verbose

# Dry run (no file creation)
python 0_main.py --prefix "VIZ" --dry-run

# Test modes
python 0_main.py --test-records-exist     # Verify API access
python 0_main.py --test-no-filter --max 3 # Inspect available fields
./0_run_test.sh                            # Quick test wrapper
```

## Architecture

```
Pimcore GraphQL API → PimcoreClient → PimcoreProduct (Pydantic) → SyncEngine → TSV Export
```

**Layers:**
1. `0_main.py` - CLI, environment loading, logging configuration
2. `pimcore_client.py` - GraphQL communication with Pimcore
3. `models.py` - Pydantic validation and business logic
4. `sync_engine.py` - TSV file generation (23 fields)

### Key Components

**PimcoreClient** (`pimcore_client.py`)
- API URL: `{base_url}/pimcore-graphql-webservices/{endpoint_name}?apikey={key}`
- Uses `getProdM06Listing` query with `PartPrefix` filter
- Flattens `ImagePrimary.id` → `image_asset_id`
- Converts None to empty strings (text) or 0.0 (numeric)

**PimcoreProduct** (`models.py`)
- Pydantic aliases map PascalCase → snake_case (e.g., `BrandName` → `brand_name`)
- Computed properties:
  - `effective_web_price`: web_price if > 0, else retail_price
  - `selected_price`: Minimum of web_price, MAP, retail (where > 0)
  - `product_title`: Brand + Model + Description (255 char limit)
  - `get_sanitized_html()`: Unescapes HTML, converts `<h2>` → `<h3>`
  - `get_plain_text_description()`: Strips all HTML tags

**SyncEngine** (`sync_engine.py`)
- Output: `{prefix}-pimcore-export-{timestamp}.tsv`
- EAR part#: alphanumeric only, hyphen after 3rd char, 20 char max
- Deep links: `https://pimcore.ear.net/admin/login/deeplink?object_{id}_object`

### Logging

- `--verbose`: DEBUG level with full API responses
- Default: WARNING level, minimal `compact` logger output

## Configuration

Required in `.env.export`:
```
PIMCORE_BASE_URL=http://pimcore.ear.net
PIMCORE_ENDPOINT_NAME=api_06
PIMCORE_API_KEY=your_api_key
```

Loaded with `override=True`. Special handling clears `PIMCORE_BASE_URL` if set to `http://localhost` before loading.

## Important Implementation Details

### GraphQL Filter Format

The Pimcore API requires a specific filter format for exact matches:
```python
filter_json = json.dumps({"PartPrefix": prefix}).replace('"', '\\"')
# Results in: filter:"{\"PartPrefix\":\"VIZ\"}"
```

This performs **exact match** filtering. If a product has `PartPrefix="Playback, VizrtVIZ"`, it will NOT match `prefix="VIZ"`.

### Field Mapping and Validation

When processing GraphQL responses:
- Extract nested `ImagePrimary.id` and flatten to `image_asset_id`
- Convert None values for optional string fields (`Description_Short`, `Description_Medium`, etc.) to empty strings
- Use Pydantic aliases consistently (GraphQL uses PascalCase, Python uses snake_case)
- Handle ValidationError exceptions gracefully - log and skip invalid products

### Price Logic

The price selection follows this priority:
1. Use `effective_web_price` (web_price if > 0, else retail_price)
2. Calculate `selected_price` as minimum of: effective_web_price, MAP, retail_price
3. Only consider prices > 0 in comparisons

### TSV Export Fields

The 23 exported fields maintain compatibility with legacy invoice systems:
- `VENDOR PART#` and `Sku`: Both use `vendor_part_number`
- `EAR part#`: Formatted version of SKU (alphanumeric only, hyphen after 3rd char, 20 char max)
- `New Invoice Description`: Uses `product_title` (255 char limit with truncation)
- `Old Invoice Description`: Plain text description (HTML tags stripped)
- `LAN LINK`: Deep link to Pimcore admin object
- `buyer/type`: Hardcoded to "COM"
- `category`: Hardcoded to "950"

## Common Development Tasks

### Adding New Pimcore Fields

1. Add field to GraphQL query in `pimcore_client.py` (both `fetch_products` and `fetch_all_products`)
2. Add field to `PimcoreProduct` model in `models.py` with appropriate alias
3. If exporting to TSV, add to fieldnames list and row mapping in `sync_engine.py`

### Debugging GraphQL Issues

Use the built-in diagnostic methods:
```python
pim_client.test_connectivity()        # Verify API access
pim_client.list_available_fields()    # Inspect object_ProdM06 schema
pim_client.list_available_queries()   # See all available queries
```

### Testing Without Creating Files

Always use `--dry-run` flag when testing to prevent file creation.

## Version History

- **v2.2.0**: Removed all legacy naming, Pimcore-to-TSV export only
- **v2.0.0**: Focused on Pimcore export only
- **v1.3.0**: Added MPN metafield support, web_price fallback, improved error handling
- **v1.2.0**: Added verbose mode, MPN support, delay optimization
