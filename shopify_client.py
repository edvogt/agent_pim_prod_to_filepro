# ============================================================================
#  shopify_client.py — Shopify API Handler
#  Version: 1.1.6
#  CHANGES: Added session reuse, improved error handling, HTTP status checks
# ============================================================================
import requests
import logging
import base64
import time
import json
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)

class ShopifyClient:
    def __init__(self, domain: str, token: str, version: str):
        """Initializes the Shopify Client with dual API support."""
        # Trim whitespace from token (common issue with env vars)
        token = token.strip() if token else ""
        
        self.admin_url = f"https://{domain}/admin/api/{version}/graphql.json"
        self.rest_url = f"https://{domain}/admin/api/{version}"
        self.headers = {
            "X-Shopify-Access-Token": token,
            "Content-Type": "application/json"
        }
        # Use session for connection pooling and reuse
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        
        # Log configuration (without exposing token)
        logger.info("=" * 80)
        logger.info("Shopify API Configuration:")
        logger.info(f"  Domain: {domain}")
        logger.info(f"  API Version: {version}")
        logger.info(f"  GraphQL URL: {self.admin_url}")
        logger.info(f"  REST URL: {self.rest_url}")
        logger.info(f"  Access Token: {'*' * min(len(token), 20)}... (hidden)")
        logger.info("=" * 80)
        
        # Test authentication
#        self._test_authentication()

    def execute_graphql(self, query: str, variables: Optional[Dict] = None) -> Dict:
        """Executes GraphQL with exponential backoff for THROTTLED status."""
        payload = {"query": query, "variables": variables or {}}
        for attempt in range(3):
            try:
                response = self.session.post(self.admin_url, json=payload)
                response.raise_for_status()
                data = response.json()
                errors = data.get("errors", [])
                if any(err.get("extensions", {}).get("code") == "THROTTLED" for err in errors):
                    wait = (attempt + 1) * 5
                    logger.warning(f"Throttled. Waiting {wait}s...")
                    time.sleep(wait)
                    continue
                return data
            except requests.RequestException as e:
                # Log more details for authentication errors
                if hasattr(e, 'response') and e.response is not None:
                    status_code = e.response.status_code
                    if status_code == 401:
                        logger.error(f"Shopify authentication failed (401 Unauthorized) - attempt {attempt + 1}/3")
                        logger.error(f"  Response: {e.response.text[:500] if e.response.text else 'No response body'}")
                        logger.error("  Please verify:")
                        logger.error("    1. Access token is correct and not expired")
                        logger.error("    2. Token has required scopes (write_products, read_products, etc.)")
                        logger.error("    3. Store domain is correct in SHOPIFY_DOMAIN_MYSHOPIFY")
                    else:
                        logger.error(f"GraphQL request error (attempt {attempt + 1}/3): {e} - Status: {status_code}")
                else:
                    logger.error(f"GraphQL request error (attempt {attempt + 1}/3): {e}")
                if attempt == 2:  # Last attempt
                    return {"errors": [{"message": f"Request failed: {str(e)}"}]}
                time.sleep((attempt + 1) * 2)
        return {"errors": [{"message": "Max retries exceeded"}]}

    def upsert_product(self, product_data: Dict) -> Optional[str]:
        """Creates or updates a product based on handle availability."""
        mutation = """mutation($input: ProductInput!) { 
            productCreate(input: $input) { product { id } userErrors { message } } 
        }"""
        result = self.execute_graphql(mutation, {"input": product_data})
        
        # Check for GraphQL errors first
        if "errors" in result:
            logger.error(f"GraphQL errors in productCreate: {result['errors']}")
            return None
        
        # Safely extract data with None checking
        data = result.get("data")
        if data is None:
            logger.error(f"No data in response: {result}")
            return None
        
        product_create = data.get("productCreate")
        if product_create is None:
            logger.error(f"No productCreate in response data: {data}")
            return None
        
        errors = product_create.get("userErrors", [])
        
        # If handle exists, find ID and update
        if any("taken" in err.get("message", "").lower() for err in errors):
            find_q = "query($h: String!) { productByHandle(handle: $h) { id } }"
            find_res = self.execute_graphql(find_q, {"h": product_data['handle']})
            
            if "errors" in find_res:
                logger.error(f"GraphQL errors in productByHandle: {find_res['errors']}")
                return None
            
            find_data = find_res.get("data") or {}
            product_by_handle = find_data.get("productByHandle") or {}
            gid = product_by_handle.get("id")
            
            if gid:
                upd_m = "mutation($i: ProductInput!) { productUpdate(input: $i) { product { id } userErrors { message } } }"
                product_data["id"] = gid
                upd_result = self.execute_graphql(upd_m, {"i": product_data})
                
                if "errors" in upd_result:
                    logger.error(f"GraphQL errors in productUpdate: {upd_result['errors']}")
                    return None
                
                upd_data = upd_result.get("data") or {}
                upd_product_update = upd_data.get("productUpdate") or {}
                upd_errors = upd_product_update.get("userErrors", [])
                
                if upd_errors:
                    logger.error(f"Product update errors for handle '{product_data['handle']}': {upd_errors}")
                else:
                    logger.info(f"Product updated successfully: {gid}")
                return gid
        
        product = product_create.get("product")
        if product is None:
            if errors:
                logger.error(f"Product create failed with user errors: {errors}")
            else:
                logger.error(f"No product in productCreate response: {product_create}")
            return None
        
        product_id = product.get("id")
        if not product_id:
            logger.error(f"No product ID returned. Errors: {errors}, Response: {product_create}")
            return None
        
        logger.info(f"Product created successfully: {product_id}")
        return product_id

    def sync_variant(self, product_gid: str, sku: str, price: str, barcode: str) -> Optional[str]:
        """Updates pricing and enables 'Continue selling when out of stock'."""
        p_id = product_gid.split("/")[-1]
        v_url = f"{self.rest_url}/products/{p_id}/variants.json"
        try:
            v_res = self.session.get(v_url)
            v_res.raise_for_status()
            v_data = v_res.json()
            v_id = v_data.get("variants", [{}])[0].get("id")
            if v_id:
                payload = {"variant": {
                    "sku": sku, "price": price, "barcode": barcode or None,
                    "inventory_management": "shopify", "inventory_policy": "continue"
                }}
                put_res = self.session.put(f"{self.rest_url}/variants/{v_id}.json", json=payload)
                put_res.raise_for_status()
                return str(v_id)
        except requests.RequestException as e:
            logger.error(f"Variant sync error for product {p_id}: {e}")
        return None

    def upload_image(self, product_gid: str, image_bytes: bytes):
        """Uploads binary image as base64 attachment via REST."""
        p_id = product_gid.split("/")[-1]
        payload = {"image": {"attachment": base64.b64encode(image_bytes).decode('utf-8')}}
        try:
            response = self.session.post(f"{self.rest_url}/products/{p_id}/images.json", json=payload)
            response.raise_for_status()
            logger.info(f"Image uploaded successfully for product {p_id}")
        except requests.RequestException as e:
            logger.error(f"Image upload error for product {p_id}: {e}")
# ============================================================================
# End of shopify_client.py — Version: 1.2.0
# ============================================================================
