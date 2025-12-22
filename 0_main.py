# ============================================================================
#  0_main.py — Sync Entry Point
#  Version: 1.2.0
#  CHANGES: Removed temporary debug code, improved error handling
# ============================================================================
import os
import argparse
import logging
from dotenv import load_dotenv
from pimcore_client import PimcoreClient
from shopify_client import ShopifyClient
from sync_engine import SyncEngine

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def main():
    # Explicitly clear PIMCORE_BASE_URL if it's localhost before loading .env.export
    if os.getenv("PIMCORE_BASE_URL") == "http://localhost":
        del os.environ["PIMCORE_BASE_URL"]
    
    # Load .env.export with override to ensure it takes precedence
    load_dotenv(".env.export", override=True)
    
    logger = logging.getLogger(__name__)

    parser = argparse.ArgumentParser(description="Pimcore to Shopify Sync")
    parser.add_argument("--prefix", help="PartPrefix to filter (required unless --test-no-filter)")
    parser.add_argument("--max", type=int, default=5, help="Max products to sync")
    parser.add_argument("--dry-run", action="store_true", help="Simulate only")
    parser.add_argument("--test-no-filter", action="store_true", help="Test query without filter to inspect available fields")
    parser.add_argument("--test-records-exist", action="store_true", help="Test if any records exist on Pimcore server")
    args = parser.parse_args()

    # Validate required environment variables
    required_vars = {
        "PIMCORE_BASE_URL": os.getenv("PIMCORE_BASE_URL"),
        "PIMCORE_ENDPOINT_NAME": os.getenv("PIMCORE_ENDPOINT_NAME"),
        "PIMCORE_API_KEY": os.getenv("PIMCORE_API_KEY"),
        "SHOPIFY_DOMAIN_MYSHOPIFY": os.getenv("SHOPIFY_DOMAIN_MYSHOPIFY"),
        "SHOPIFY_ADMIN_TOKEN": os.getenv("SHOPIFY_ADMIN_TOKEN"),
        "SHOPIFY_API_VERSION": os.getenv("SHOPIFY_API_VERSION")
    }
    
    missing = [var for var, value in required_vars.items() if not value]
    if missing:
        logger.error(f"Missing required environment variables: {', '.join(missing)}")
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

    # Display configuration for verification
    logger.info("=" * 80)
    logger.info("Configuration Summary:")
    logger.info(f"  PIMCORE_BASE_URL: {required_vars['PIMCORE_BASE_URL']}")
    logger.info(f"  PIMCORE_ENDPOINT_NAME: {required_vars['PIMCORE_ENDPOINT_NAME']}")
    logger.info(f"  PIMCORE_API_KEY: {'*' * min(len(required_vars['PIMCORE_API_KEY'] or ''), 20)}... (hidden)")
    logger.info("=" * 80)
    
    pim_client = PimcoreClient(
        base_url=required_vars["PIMCORE_BASE_URL"],
        endpoint_name=required_vars["PIMCORE_ENDPOINT_NAME"],
        api_key=required_vars["PIMCORE_API_KEY"]
    )

    # Test mode: verify records exist on server
    if args.test_records_exist:
        logger.info("=" * 80)
        logger.info("TEST: Verifying if records exist on Pimcore server")
        logger.info("=" * 80)
        
        # Test 1: Fetch all products (no filter)
        logger.info("\n[Test 1] Fetching ALL products (no filter)...")
        all_products = pim_client.fetch_all_products(limit=100)
        logger.info(f"Result: {len(all_products)} products found")
        
        # Test 2: Try with known working prefix "EAR"
        logger.info("\n[Test 2] Testing with known working prefix 'EAR'...")
        ear_query = f'''query {{
          getProdM06Listing(first: 10, filter: "{{\\"PartPrefix\\":\\\"EAR\\\"}}") {{
            edges {{
              node {{
                id
                sku
                PartPrefix
                BrandName
              }}
            }}
          }}
        }}'''
        try:
            ear_res = pim_client.session.post(pim_client.api_url, json={"query": ear_query})
            ear_res.raise_for_status()
            ear_data = ear_res.json()
            if "errors" not in ear_data:
                ear_nodes = ear_data.get("data", {}).get("getProdM06Listing", {}).get("edges", [])
                logger.info(f"Result: {len(ear_nodes)} products with PartPrefix='EAR' found")
                if len(ear_nodes) > 0:
                    sample = ear_nodes[0].get("node", {})
                    logger.info(f"  Sample: SKU={sample.get('sku')}, PartPrefix={sample.get('PartPrefix')}")
        except Exception as e:
            logger.error(f"EAR test failed: {e}")
        
        # Test 3: Try with prefix "VIZ" using exact match
        logger.info("\n[Test 3] Testing with prefix 'VIZ' (exact match)...")
        viz_query = f'''query {{
          getProdM06Listing(first: 10, filter: "{{\\"PartPrefix\\":\\\"VIZ\\\"}}") {{
            edges {{
              node {{
                id
                sku
                PartPrefix
              }}
            }}
          }}
        }}'''
        try:
            viz_res = pim_client.session.post(pim_client.api_url, json={"query": viz_query})
            viz_res.raise_for_status()
            viz_data = viz_res.json()
            if "errors" not in viz_data:
                viz_nodes = viz_data.get("data", {}).get("getProdM06Listing", {}).get("edges", [])
                logger.info(f"Result: {len(viz_nodes)} products with PartPrefix='VIZ' (exact) found")
        except Exception as e:
            logger.error(f"VIZ exact test failed: {e}")
        
        # Test 4: Summary
        logger.info("\n" + "=" * 80)
        logger.info("SUMMARY:")
        logger.info(f"  • Total products accessible (no filter): {len(all_products)}")
        logger.info(f"  • API endpoint: {pim_client.api_url.split('?')[0]}")
        logger.info("=" * 80)
        
        if len(all_products) == 0:
            logger.warning("\n⚠️  NO PRODUCTS FOUND - Possible issues:")
            logger.warning("  1. Products may not be published")
            logger.warning("  2. API may require specific permissions")
            logger.warning("  3. Products may not be accessible via this endpoint")
            logger.warning("  4. Check Pimcore admin to verify products exist and are published")
        else:
            logger.info(f"\n✅ {len(all_products)} products are accessible via API")
            if len(all_products) > 0:
                sample = all_products[0]
                logger.info(f"   Sample product: SKU={sample.sku}, Brand={sample.brand_name}")
        
        return

    # Test mode: fetch products without filter
    if args.test_no_filter:
        logger.info("=" * 80)
        logger.info("TEST MODE: Fetching products WITHOUT filter to inspect available fields")
        logger.info("=" * 80)
        products = pim_client.fetch_all_products(limit=args.max)
        logger.info("=" * 80)
        logger.info(f"Results: Found {len(products)} product(s)")
        logger.info("=" * 80)
        
        for i, p in enumerate(products, 1):
            logger.info(f"\nProduct {i}:")
            logger.info(f"  ID: {p.id}")
            logger.info(f"  SKU: {p.sku}")
            logger.info(f"  Brand: {p.brand_name}")
            logger.info(f"  Model: {p.model}")
            logger.info(f"  Vendor Part Number: {p.vendor_part_number}")
            logger.info(f"  Image Asset ID: {p.image_asset_id}")
        return

    # Normal sync mode
    if not args.prefix:
        logger.error("--prefix is required unless using --test-no-filter")
        parser.print_help()
        return

    # Trim whitespace from Shopify token (common issue with .env files)
    shopify_token = (required_vars["SHOPIFY_ADMIN_TOKEN"] or "").strip()
    # Remove quotes if present (common .env file issue)
    shopify_token = shopify_token.strip('"\'').strip()
    shopify_domain = (required_vars["SHOPIFY_DOMAIN_MYSHOPIFY"] or "").strip()
    
    shop_client = ShopifyClient(
        domain=shopify_domain,
        token=shopify_token,
        version=required_vars["SHOPIFY_API_VERSION"]
    )

    config = {
        "MAX_PRODUCTS": args.max,
        "DRY_RUN": args.dry_run,
        "DELAY_BETWEEN_PRODUCTS": int(os.getenv("DELAY_BETWEEN_PRODUCTS", 2)),
        "DELAY_AFTER_IMAGE": int(os.getenv("DELAY_AFTER_IMAGE", 3))
    }

    engine = SyncEngine(pim_client, shop_client, config)
    engine.run(part_prefix=args.prefix)

if __name__ == "__main__":
    main()
# ============================================================================
# End of 0_main.py — Version: 1.2.0
# ============================================================================
