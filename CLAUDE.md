# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Pimcore PIM data export tool that fetches product data from Pimcore using GraphQL API and exports to tab-delimited TSV files for import into FilePro (legacy invoice system).

## Development Commands

```bash
# Setup
python -m venv venv && source venv/bin/activate && pip install -r requirements.txt

# Export products to TSV (outputs to exports/ directory)
python 0_main.py --prefix "VIZ" --max 10

# Verbose mode (DEBUG logging)
python 0_main.py --prefix "EAR" --max 5 --verbose

# Dry run (no file creation)
python 0_main.py --prefix "VIZ" --dry-run

# Test modes
python 0_main.py --test-records-exist     # Verify API access (tests unfiltered, EAR, VIZ)
python 0_main.py --test-no-filter --max 3 # Inspect available fields (raw product structure)
./0_run_test.sh                            # Quick test: --prefix "EAR" --max 1 --dry-run

# Import TSV to FilePro (must run as filepro user)
./stimport path/to/file.tsv               # Import existing TSV file
./stimport BRD                            # Export prefix from Pimcore, then import
./stimport --dry-run path/to/file.tsv     # Simulate import
./stimport --skip-user-check file.tsv     # Bypass filepro user check (testing)
```

**CLI defaults**: `--max` defaults to 5 for `0_main.py`, but stimport uses 10000 when exporting from Pimcore.

## Logging

Two logging modes controlled by `--verbose`:
- **Compact mode** (default): WARNING level for main logger; "compact" logger outputs plain messages (no timestamps) for export summaries
- **Verbose mode**: DEBUG level, detailed field-by-field output per product

No formal test suite — testing is done via CLI flags (`--test-records-exist`, `--test-no-filter`, `--dry-run`) and `0_run_test.sh`.

## Architecture

```
Pimcore GraphQL API → PimcoreClient → PimcoreProduct (Pydantic) → SyncEngine → TSV Export
                                                                                    ↓
                                                                            stimport → FilePro
```

**Core Files:**
- `0_main.py` - CLI entry point, environment loading, logging configuration
- `pimcore_client.py` - GraphQL communication with Pimcore API
- `models.py` - Pydantic validation and business logic (price calculation, title generation)
- `sync_engine.py` - TSV file generation (23 fields for legacy invoice systems)
- `stimport` - Python script that imports TSV files into FilePro database (despite no `.py` extension)

### PimcoreClient (`pimcore_client.py`)
- API URL format: `{base_url}/pimcore-graphql-webservices/{endpoint_name}?apikey={key}`
- Tests connectivity on `__init__` via a minimal `getProdM07Listing(first: 1)` query
- Uses `getProdM07Listing` query with `PartPrefix` filter (exact match)
- Flattens `ImagePrimary.id` → `image_asset_id`
- Converts None to empty strings (text) or 0.0 (numeric) before Pydantic validation
- `get_asset_data()` fetches image binary via base64-encoded GraphQL response
- Three methods fetch products: `fetch_products` (filtered), `fetch_all_products` (unfiltered), `fetch_products_no_filter` (test/debug)

### PimcoreProduct (`models.py`)
- Pydantic v2 model using `Field(alias=...)` to map PascalCase API fields → snake_case (e.g., `BrandName` → `brand_name`)
- Model is constructed with API field names (aliases), not Python attribute names
- Key computed properties:
  - `effective_web_price`: web_price if > 0, else retail_price
  - `selected_price`: Returns **string** — minimum of web_price, MAP, retail (where > 0)
  - `product_title`: Brand + (Model or VendorPartNumber) + Description_Short (255 char limit, truncates at word boundary with "...")
  - `get_sanitized_html()`: Combines Description_Medium + Specifications_WYSIWYG, unescapes HTML, converts `<h2>` → `<h3>`
  - `get_plain_text_description()`: Strips all HTML tags from Description_Medium only

### SyncEngine (`sync_engine.py`)
- Output: `exports/{prefix}-pimcore-export-{timestamp}.tsv` (tab-delimited, UTF-8)
- EAR part# format: strip non-alphanumeric from SKU, hyphen after 3rd char, max 20 chars. If too long, uses `first4 + last3 + remaining` truncation.
- Deep links: `https://pimcore.ear.net/admin/login/deeplink?object_{id}_object`
- Hardcoded fields: `buyer/type` = "COM", `category` = "950"
- TSV field mappings not obvious from names: `Vendor#` → `part_prefix`, `Flag` → `upc`, `comment` → `Pimcore asset: {id}`
- Description sanitization (applied to both New/Old Invoice Description): removes brand/SKU, replaces " / " with "/", " - " with "-", " with " with "/", strips non-alphanumeric (except `/- `), removes duplicate words. Old Invoice Description additionally replaces " for " with " ".

### stimport CLI (`stimport`)
- **Python script** (not bash) — `#!/usr/bin/env python3`
- **Two modes**: Import existing TSV file OR export from Pimcore + import
  - `./stimport path/to/file.tsv` - Import existing TSV
  - `./stimport BRD` - 3-char alphabetic argument triggers Pimcore export (`0_main.py --prefix BRD --max 10000`) first, then imports the result
  - No argument prompts for interactive input
- Cleans TSV files: strips non-printable/non-ASCII chars, removes double-quotes, empty lines, comment lines (# or "# patterns)
- Processing pipeline: raw file → `stimport-raw.txt` → iconv → `stimport-UTF.txt` → sed-like formatting → `stimport.txt`
- Imports to FilePro using `dreport sel -f tabimport` command
- Requires `filepro` user (bypass with `--skip-user-check` for testing)
- Archives old TSV files automatically (keeps 5 most recent in `exports/archive/`)
- FilePro config paths: `/appl/fpmerge/` (working files), `/appl/fp/` (dreport binary)

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

The Pimcore API requires exact match filtering:
```python
filter_json = json.dumps({"PartPrefix": prefix}).replace('"', '\\"')
# Results in: filter:"{\"PartPrefix\":\"VIZ\"}"
```

Products with `PartPrefix="Playback, VizrtVIZ"` will NOT match `prefix="VIZ"`.

### Price Logic

1. Use `effective_web_price` (web_price if > 0, else retail_price)
2. Calculate `selected_price` as minimum of: effective_web_price, MAP, retail_price
3. Only consider prices > 0 in comparisons
4. `selected_price` returns a **string** (not float)

### TSV Export Fields (23 total)

The exported fields maintain compatibility with legacy invoice systems:
- `MPN` and `Sku`: Both use `vendor_part_number`
- `EAR part#`: Formatted SKU (alphanumeric, hyphen after 3rd char, max 20 chars)
- `New Invoice Description`: `product_title` (255 char limit, brand/SKU removed)
- `Old Invoice Description`: Plain text description (HTML stripped, brand/SKU removed)
- `LAN LINK`: Deep link to Pimcore admin object
- `retail`: Uses `selected_price` (minimum of available prices)
- `Vendor#` and `Part# Prefix`: Both use `part_prefix`

### Adding New Pimcore Fields

1. Add field to GraphQL query in `pimcore_client.py` (in `fetch_products`, `fetch_all_products`, **and** `fetch_products_no_filter`)
2. Add field to `PimcoreProduct` model in `models.py` with appropriate `Field(alias=...)` for PascalCase mapping
3. If exporting to TSV, add to `fieldnames` list and `row` dict in `sync_engine.py`

### Debugging GraphQL Issues

Use the built-in diagnostic methods:
```python
pim_client.test_connectivity()        # Verify API access
pim_client.list_available_fields()    # Inspect object_ProdM07 schema
pim_client.list_available_queries()   # See all available queries
```
