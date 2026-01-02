# ============================================================================
#  sync_engine.py — Orchestration Engine
#  Version: 1.3.0
#  CHANGES: Improved error handling and logging, added MPN metafield support, verbose mode with compact output
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

    def run(self, part_prefix: str, verbose: bool = False):
        """Executes the main sync loop for the specified prefix."""
        if verbose:
            logger.info(f"Starting Sync for Prefix: {part_prefix}")
        
        products = self.pimcore.fetch_products(part_prefix, self.config['MAX_PRODUCTS'])
        
        if not products:
            if verbose:
                logger.warning(f"No products found for prefix '{part_prefix}'")
            else:
                compact_logger = logging.getLogger('compact')
                compact_logger.warning(f"No products found for prefix '{part_prefix}'")
            return
        
        total = len(products)
        
        # Print header in compact mode
        if not verbose:
            compact_logger = logging.getLogger('compact')
            compact_logger.info("SKU,Status Image,Status Completed,Item# of Total")
        
        if verbose:
            logger.info(f"Processing {total} product(s)")
        
        for i, p in enumerate(products, 1):
            if verbose:
                logger.info(f"[{i}/{total}] Syncing SKU: {p.sku}")
            
            if self.config.get('DRY_RUN'):
                if verbose:
                    logger.info(f"DRY-RUN: Skipping {p.sku}")
                else:
                    compact_logger = logging.getLogger('compact')
                    compact_logger.info(f"{p.sku},-,DRY-RUN,{i}/{total}")
                continue

            image_status = ""
            completed_status = ""
            
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
                # Pass vendor_part_number as MPN (Manufacturer Part Number)
                self.shopify.sync_variant(p_gid, p.sku, p.selected_price, p.upc, mpn=p.vendor_part_number)
                if p.image_asset_id:
                    img = self.pimcore.get_asset_data(p.image_asset_id)
                    if img:
                        try:
                            self.shopify.upload_image(p_gid, img)
                            image_status = "✓"
                            if verbose:
                                logger.info(f"Image uploaded successfully")
                        except Exception as e:
                            image_status = "✗"
                            if verbose:
                                logger.error(f"Image upload failed: {e}")
                    else:
                        image_status = "-"
                        if verbose:
                            logger.warning(f"No image data retrieved")
                else:
                    image_status = "-"
                    if verbose:
                        logger.debug(f"No image_asset_id for {p.sku}")
                
                completed_status = "✓"
                if verbose:
                    logger.info(f"Product sync completed")
                
                time.sleep(self.config.get('DELAY_AFTER_IMAGE', 1.5))
            else:
                completed_status = "✗"
                if verbose:
                    logger.error(f"Product creation/update failed")
            
            # 3. Compact output
            if not verbose:
                compact_logger = logging.getLogger('compact')
                compact_logger.info(f"{p.sku},{image_status},{completed_status},{i}/{total}")
            
            # 4. Throttle delay
            time.sleep(self.config.get('DELAY_BETWEEN_PRODUCTS', 1.5))
        
        if verbose:
            logger.info("Sync Process Finished")
        else:
            compact_logger = logging.getLogger('compact')
            compact_logger.info(f"Sync completed: {total} product(s) processed")
# ============================================================================
# End of sync_engine.py — Version: 1.3.0
# ============================================================================
