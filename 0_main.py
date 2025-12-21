import os
import argparse
from dotenv import load_dotenv

# Import the logic modules you created in Steps 2-5
from pimcore_client import PimcoreClient
from shopify_client import ShopifyClient
from sync_engine import SyncEngine

def main():
    # Load settings from the existing environment file
    load_dotenv(".env.export")

    # Command line argument parsing for flexible execution
    parser = argparse.ArgumentParser(description="Pimcore to Shopify Sync Entry Point")
    parser.add_argument("--prefix", required=True, help="PartPrefix to filter (e.g., EAR)")
    parser.add_argument("--max", type=int, default=5, help="Max products to sync")
    parser.add_argument("--dry-run", action="store_true", help="Simulate sync without writing")
    args = parser.parse_args()

    # Initialize the Source Client (Pimcore)
    pim_client = PimcoreClient(
        base_url=os.getenv("PIMCORE_BASE_URL"),
        endpoint_name=os.getenv("PIMCORE_ENDPOINT_NAME"),
        api_key=os.getenv("PIMCORE_API_KEY")
    )

    # Initialize the Destination Client (Shopify)
    shop_client = ShopifyClient(
        domain=os.getenv("SHOPIFY_DOMAIN_MYSHOPIFY"),
        token=os.getenv("SHOPIFY_ADMIN_TOKEN"),
        version=os.getenv("SHOPIFY_API_VERSION")
    )

    # Consolidate configuration into a single object for the engine
    config = {
        "MAX_PRODUCTS": args.max,
        "DRY_RUN": args.dry_run,
        "DELAY_BETWEEN_PRODUCTS": int(os.getenv("DELAY_BETWEEN_PRODUCTS", 2)),
        "DELAY_AFTER_IMAGE": int(os.getenv("DELAY_AFTER_IMAGE", 3))
    }

    # Start the orchestration engine
    engine = SyncEngine(pim_client, shop_client, config)
    engine.run(part_prefix=args.prefix)

if __name__ == "__main__":
    main()
