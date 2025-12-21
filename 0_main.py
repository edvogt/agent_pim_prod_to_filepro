# ============================================================================
#  0_main.py — Sync Entry Point
#  Version: 1.1.2
# ============================================================================
import os
import argparse
from dotenv import load_dotenv
from pimcore_client import PimcoreClient
from shopify_client import ShopifyClient
from sync_engine import SyncEngine

def main():
    load_dotenv(".env.export") #

    parser = argparse.ArgumentParser(description="Pimcore to Shopify Sync")
    parser.add_argument("--prefix", required=True, help="PartPrefix to filter")
    parser.add_argument("--max", type=int, default=5, help="Max products to sync")
    parser.add_argument("--dry-run", action="store_true", help="Simulate only")
    args = parser.parse_args()

    pim_client = PimcoreClient(
        base_url=os.getenv("PIMCORE_BASE_URL"),
        endpoint_name=os.getenv("PIMCORE_ENDPOINT_NAME"),
        api_key=os.getenv("PIMCORE_API_KEY")
    )

    shop_client = ShopifyClient(
        domain=os.getenv("SHOPIFY_DOMAIN_MYSHOPIFY"),
        token=os.getenv("SHOPIFY_ADMIN_TOKEN"),
        version=os.getenv("SHOPIFY_API_VERSION")
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
# End of 0_main.py — Version: 1.1.2
# ============================================================================
