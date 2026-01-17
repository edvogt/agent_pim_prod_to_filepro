# ============================================================================
#  sync_engine.py — Product Export Engine
#  Version: 2.2.0
#  Exports Pimcore products to tab-delimited TSV for legacy invoice systems
# ============================================================================
import logging
import csv
import re
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
        
        # Define CSV header with fields for legacy invoice systems
        fieldnames = [
            'VENDOR PART#',
            'EAR part#',
            'New Invoice Description',
            'Old Invoice Description',
            'comment',
            'Cost',
            'retail',
            'web price',
            'Part# Prefix',
            'buyer/type',
            'Vendor#',
            'Descrip Vendor Name',
            'category',
            'Flag',
            'WAN LINK',
            'LAN LINK',
            'weight(lbs)',
            'MAP',
            'IMAGE',
            'CAP FILE',
            'caption text',
            'Sku',
            'UPC'
        ]
        
        # Write CSV file with tab delimiter
        try:
            with open(self.output_file, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames, delimiter='\t')
                
                # Write header row
                writer.writeheader()
                
                # Helper to format EAR part#
                def format_ear_part(sku):
                    cleaned = re.sub(r'[^a-zA-Z0-9]', '', sku)
                    formatted = cleaned[:3] + '-' + cleaned[3:]
                    if len(formatted) > 20:
                        formatted = formatted[:4] + formatted[-3:] + formatted[7:]
                    return formatted[:20]

                # Write product rows
                for i, p in enumerate(products, 1):
                    if verbose:
                        logger.info(f"[{i}/{total}] Exporting SKU: {p.sku}")
                    
                    # Helper to sanitize description fields
                    def sanitize_description(text, sku=None, brand=None):
                        if not text:
                            return ""
                        # Remove all occurrences of brand name
                        if brand:
                            text = re.sub(re.escape(brand) + r'\s*', '', text, flags=re.IGNORECASE)
                        # Remove SKU from beginning
                        if sku:
                            text = re.sub(r'^' + re.escape(sku) + r'\s+', '', text)
                        # Replace " / " with "/" and " - " with "-"
                        text = text.replace(" / ", "/")
                        text = text.replace(" - ", "-")
                        # Keep only a-z, A-Z, 0-9, /, -, and space
                        text = re.sub(r'[^a-zA-Z0-9/\- ]', '', text)
                        # Collapse multiple spaces
                        text = re.sub(r' +', ' ', text)
                        # Remove duplicate words (case-insensitive)
                        words = text.split()
                        seen = set()
                        unique_words = []
                        for word in words:
                            word_lower = word.lower()
                            if word_lower not in seen:
                                seen.add(word_lower)
                                unique_words.append(word)
                        text = ' '.join(unique_words)
                        return text.strip()

                    # Prepare row data for legacy invoice systems
                    row = {
                        'VENDOR PART#': p.vendor_part_number,
                        'EAR part#': format_ear_part(p.sku),
                        'New Invoice Description': sanitize_description(p.product_title, p.vendor_part_number, p.brand_name),
                        'Old Invoice Description': sanitize_description(p.get_plain_text_description(), p.vendor_part_number, p.brand_name).replace(' for ', ' '),
                        'comment': f'Pimcore asset: {p.id}',
                        'Cost': p.cost or '',
                        'retail': p.selected_price,
                        'web price': p.web_price or '',
                        'Part# Prefix': p.part_prefix or '',
                        'buyer/type': 'COM',
                        'Descrip Vendor Name': p.brand_name,
                        'Vendor#': p.part_prefix or '',
                        'category': '950',
                        'Flag': p.upc or '',
                        'WAN LINK': p.product_webpage or '',
                        'LAN LINK': f'https://pimcore.ear.net/admin/login/deeplink?object_{p.id}_object',
                        'weight(lbs)': p.weight or '',
                        'MAP': p.map_price or '',
                        'IMAGE': '',
                        'CAP FILE': '',
                        'caption text': '',
                        'Sku': p.vendor_part_number,
                        'UPC': p.upc or ''
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
# End of sync_engine.py — Version: 2.2.0
# ============================================================================
