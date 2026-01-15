# ============================================================================
#  sync_engine.py — Product Fetching Engine
#  Version: 2.1.0
#  CHANGES: Added CSV export functionality with tab-delimited format containing fields previously sent to Shopify
# ============================================================================
import logging
import csv
from datetime import datetime
from pimcore_client import PimcoreClient

logger = logging.getLogger(__name__)

class SyncEngine:
    def __init__(self, pimcore: PimcoreClient, config: dict):
        """Initializes engine with Pimcore client."""
        self.pimcore = pimcore
        self.config = config

    def run(self, part_prefix: str, verbose: bool = False):
        """Fetches products and exports to tab-delimited CSV file."""
        # Generate output filename with prefix and timestamp
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.output_file = f"{part_prefix}-pimcore-export-{timestamp}.tsv"

        if verbose:
            logger.info(f"Starting Product Fetch for Prefix: {part_prefix}")
        
        products = self.pimcore.fetch_products(part_prefix, self.config['MAX_PRODUCTS'])
        
        if not products:
            if verbose:
                logger.warning(f"No products found for prefix '{part_prefix}'")
            else:
                compact_logger = logging.getLogger('compact')
                compact_logger.warning(f"No products found for prefix '{part_prefix}'")
            return
        
        total = len(products)
        
        if verbose:
            logger.info(f"Processing {total} product(s)")
            logger.info(f"Writing output to: {self.output_file}")
        
        # Define CSV header with fields previously sent to Shopify
        fieldnames = [
            'title',
            'description',
            'vendor',
            'handle',
            'status',
            'sku',
            'price',
            'barcode',
            'mpn',
            'image_asset_id'
        ]
        
        # Write CSV file with tab delimiter
        try:
            with open(self.output_file, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames, delimiter='\t')
                
                # Write header row
                writer.writeheader()
                
                # Write product rows
                for i, p in enumerate(products, 1):
                    if verbose:
                        logger.info(f"[{i}/{total}] Exporting SKU: {p.sku}")
                    
                    # Prepare row data with fields previously sent to Shopify
                    row = {
                        'title': p.shopify_title,
                        'description': p.get_plain_text_description(),
                        'vendor': p.brand_name,
                        'handle': p.sku.lower().replace(" ", "-"),
                        'status': 'ACTIVE',
                        'sku': p.sku,
                        'price': p.selected_price,
                        'barcode': p.upc or '',
                        'mpn': p.vendor_part_number,
                        'image_asset_id': p.image_asset_id or ''
                    }
                    
                    writer.writerow(row)
            
            if verbose:
                logger.info(f"Successfully exported {total} product(s) to {self.output_file}")
            else:
                compact_logger = logging.getLogger('compact')
                compact_logger.info(f"Exported {total} product(s) to {self.output_file}")
                
        except Exception as e:
            logger.error(f"Error writing CSV file: {e}")
            raise
# ============================================================================
# End of sync_engine.py — Version: 1.3.0
# ============================================================================
