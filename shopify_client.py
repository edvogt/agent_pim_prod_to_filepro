# ============================================================================
#  shopify_client.py — Shopify API Handler
#  Version: 1.1.5
# ============================================================================
import requests
import logging
import base64
import time
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)

class ShopifyClient:
    def __init__(self, domain: str, token: str, version: str):
        """Initializes the Shopify Client with dual API support."""
        self.admin_url = f"https://{domain}/admin/api/{version}/graphql.json"
        self.rest_url = f"https://{domain}/admin/api/{version}"
        self.headers = {
            "X-Shopify-Access-Token": token,
            "Content-Type": "application/json"
        }

    def execute_graphql(self, query: str, variables: Optional[Dict] = None) -> Dict:
        """Executes GraphQL with exponential backoff for THROTTLED status."""
        payload = {"query": query, "variables": variables or {}}
        for attempt in range(3):
            response = requests.post(self.admin_url, json=payload, headers=self.headers)
            data = response.json()
            errors = data.get("errors", [])
            if any(err.get("extensions", {}).get("code") == "THROTTLED" for err in errors):
                wait = (attempt + 1) * 5
                logger.warning(f"Throttled. Waiting {wait}s...")
                time.sleep(wait)
                continue
            return data
        return {"errors": [{"message": "Max retries exceeded"}]}

    def upsert_product(self, product_data: Dict) -> Optional[str]:
        """Creates or updates a product based on handle availability."""
        mutation = """mutation($input: ProductInput!) { 
            productCreate(input: $input) { product { id } userErrors { message } } 
        }"""
        result = self.execute_graphql(mutation, {"input": product_data})
        errors = result.get("data", {}).get("productCreate", {}).get("userErrors", [])
        
        # If handle exists, find ID and update
        if any("taken" in err.get("message", "").lower() for err in errors):
            find_q = "query($h: String!) { productByHandle(handle: $h) { id } }"
            find_res = self.execute_graphql(find_q, {"h": product_data['handle']})
            gid = find_res.get("data", {}).get("productByHandle", {}).get("id")
            if gid:
                upd_m = "mutation($i: ProductInput!) { productUpdate(input: $i) { product { id } } }"
                product_data["id"] = gid
                self.execute_graphql(upd_m, {"i": product_data})
                return gid
        return result.get("data", {}).get("productCreate", {}).get("product", {}).get("id")

    def sync_variant(self, product_gid: str, sku: str, price: str, barcode: str):
        """Updates pricing and enables 'Continue selling when out of stock'."""
        p_id = product_gid.split("/")[-1]
        v_url = f"{self.rest_url}/products/{p_id}/variants.json"
        v_res = requests.get(v_url, headers=self.headers).json()
        v_id = v_res.get("variants", [{}])[0].get("id")
        if v_id:
            payload = {"variant": {
                "sku": sku, "price": price, "barcode": barcode or None,
                "inventory_management": "shopify", "inventory_policy": "continue" #
            }}
            requests.put(f"{self.rest_url}/variants/{v_id}.json", json=payload, headers=self.headers)

    def upload_image(self, product_gid: str, image_bytes: bytes):
        """Uploads binary image as base64 attachment via REST."""
        p_id = product_gid.split("/")[-1]
        payload = {"image": {"attachment": base64.b64encode(image_bytes).decode('utf-8')}}
        requests.post(f"{self.rest_url}/products/{p_id}/images.json", json=payload, headers=self.headers)
# ============================================================================
# End of shopify_client.py — Version: 1.1.5
# ============================================================================
