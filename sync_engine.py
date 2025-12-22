# ============================================================================
#  sync_engine.py — Orchestration Engine
#  Version: 1.2.0
#  CHANGES: Improved error handling and logging
# ============================================================================
import logging
import time
from pimcore_client import PimcoreClient
from shopify_client import ShopifyClient

logger = logging.getLogger(__name__)

class SyncEngine:
    def __init__(self, pimcore: PimcoreClient, shopify: ShopifyClient, config: dict):
        """Initializes engine with source and destination clients."""
        self.pimcore = pimcore
        self.shopify = shopify
        self.config = config

    def run(self, part_prefix: str):
        """Executes the main sync loop for the specified prefix."""
        logger.info(f"Starting Sync for Prefix: {part_prefix}")
        products = self.pimcore.fetch_products(part_prefix, self.config['MAX_PRODUCTS'])
        
        if not products:
            logger.warning(f"No products found for prefix '{part_prefix}'")
            return
        
        logger.info(f"Processing {len(products)} product(s)")
        for i, p in enumerate(products):
            logger.info(f"[{i+1}/{len(products)}] Syncing SKU: {p.sku}")
            
            if self.config.get('DRY_RUN'):
                logger.info(f"DRY-RUN: Skipping {p.sku}")
                continue

            # 1. Product Upsert
            p_gid = self.shopify.upsert_product({
                "title": p.shopify_title,
                "descriptionHtml": p.get_sanitized_html(),
                "vendor": p.brand_name,
                "handle": p.sku.lower().replace(" ", "-"),
                "status": "ACTIVE"
            })

            # 2. Variant & Image Sync
            if p_gid:
                self.shopify.sync_variant(p_gid, p.sku, p.selected_price, p.upc)
                if p.image_asset_id:
                    img = self.pimcore.get_asset_data(p.image_asset_id)
                    if img:
                        self.shopify.upload_image(p_gid, img)
                        time.sleep(self.config.get('DELAY_AFTER_IMAGE', 3))

            # 3. Throttle delay
            time.sleep(self.config.get('DELAY_BETWEEN_PRODUCTS', 2))
        
        logger.info("Sync Process Finished")
# ============================================================================
# End of sync_engine.py — Version: 1.2.0
# ============================================================================
