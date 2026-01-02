# ============================================================================
#  shopify_client.py — Shopify API Handler
#  Version: 1.2.1
#  CHANGES: Added session reuse, improved error handling, HTTP status checks, MPN metafield support (custom.vendor_part)
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

    def get_variant_metafields(self, variant_gid: str) -> List[Dict]:
        """Queries all metafields on a product variant."""
        query = """
        query getVariantMetafields($ownerId: ID!, $first: Int!) {
            metafields(ownerId: $ownerId, first: $first) {
                edges {
                    node {
                        id
                        namespace
                        key
                        value
                        type
                    }
                }
            }
        }
        """
        variables = {
            "ownerId": variant_gid,
            "first": 50
        }
        try:
            result = self.execute_graphql(query, variables)
            if "errors" in result:
                logger.debug(f"Error querying metafields for variant {variant_gid}: {result['errors']}")
                return []
            
            data = result.get("data", {})
            metafields_data = data.get("metafields", {})
            edges = metafields_data.get("edges", [])
            metafields = [edge.get("node") for edge in edges if edge.get("node")]
            
            if metafields:
                logger.info(f"   Found {len(metafields)} metafield(s) on variant:")
                for mf in metafields:
                    logger.info(f"     - {mf.get('namespace')}.{mf.get('key')} = '{mf.get('value')}' (type: {mf.get('type')})")
            else:
                logger.info(f"   No metafields found on this variant (it's a new variant with no metafields yet)")
            return metafields
        except Exception as e:
            logger.debug(f"Exception querying metafields for variant {variant_gid}: {e}")
            return []

    def get_variant_metafield(self, variant_gid: str, namespace: str, key: str) -> Optional[Dict]:
        """Queries a specific metafield on a product variant to verify it exists and get its value."""
        query = """
        query getVariantMetafield($ownerId: ID!, $namespace: String!, $key: String!) {
            metafield(ownerId: $ownerId, namespace: $namespace, key: $key) {
                id
                namespace
                key
                value
                type
            }
        }
        """
        variables = {
            "ownerId": variant_gid,
            "namespace": namespace,
            "key": key
        }
        try:
            result = self.execute_graphql(query, variables)
            if "errors" in result:
                logger.debug(f"Error querying metafield {namespace}.{key}: {result['errors']}")
                return None
            
            data = result.get("data", {})
            metafield = data.get("metafield")
            if metafield:
                logger.debug(f"Found existing metafield {namespace}.{key}: {metafield.get('value')} (type: {metafield.get('type')})")
            return metafield
        except Exception as e:
            logger.debug(f"Exception querying metafield {namespace}.{key}: {e}")
            return None

    def set_variant_metafield(self, variant_gid: str, namespace: str, key: str, value: str) -> bool:
        """Sets a metafield on a product variant using GraphQL metafieldSet mutation.
        Matches Shopify's recommended MetafieldsSet mutation format."""
        mutation = """
        mutation MetafieldsSet($metafields: [MetafieldsSetInput!]!) {
            metafieldsSet(metafields: $metafields) {
                metafields {
                    key
                    namespace
                    value
                    updatedAt
                }
                userErrors {
                    field
                    message
                    code
                }
            }
        }
        """
        variables = {
            "metafields": [{
                "ownerId": variant_gid,
                "namespace": namespace,
                "key": key,
                "type": "single_line_text_field",
                "value": value
            }]
        }
        try:
            logger.info(f"🔧 Attempting to set metafield {namespace}.{key} = '{value}' for variant {variant_gid}")
            logger.debug(f"Variables being sent: {json.dumps(variables, indent=2)}")
            result = self.execute_graphql(mutation, variables)
            
            # Log full response for debugging
            logger.debug(f"Full GraphQL response for {namespace}.{key}: {json.dumps(result, indent=2)}")
            
            if "errors" in result:
                logger.error(f"❌ GraphQL errors in metafieldSet for {namespace}.{key}: {json.dumps(result['errors'], indent=2)}")
                return False
            
            data = result.get("data")
            if data is None:
                logger.error(f"❌ No 'data' field in response for {namespace}.{key}. Full response: {json.dumps(result, indent=2)}")
                return False
            
            metafields_set = data.get("metafieldsSet", {})
            if not metafields_set:
                logger.error(f"❌ No 'metafieldsSet' in data for {namespace}.{key}. Data: {json.dumps(data, indent=2)}")
                return False
            
            user_errors = metafields_set.get("userErrors", [])
            
            if user_errors:
                logger.error(f"❌ Metafield set userErrors for {namespace}.{key} on variant {variant_gid}:")
                for error in user_errors:
                    logger.error(f"   - Field: {error.get('field')}, Message: {error.get('message')}, Code: {error.get('code')}")
                logger.error(f"   Full userErrors: {json.dumps(user_errors, indent=2)}")
                return False
            
            # Check if metafield was actually set
            metafields = metafields_set.get("metafields", [])
            if metafields and len(metafields) > 0:
                set_metafield = metafields[0]
                actual_value = set_metafield.get('value')
                actual_namespace = set_metafield.get('namespace')
                actual_key = set_metafield.get('key')
                
                # Verify the metafield returned matches what we requested
                if actual_namespace == namespace and actual_key == key:
                    logger.info(f"✅ Metafield set successfully: {namespace}.{key} = '{actual_value}' (updatedAt: {set_metafield.get('updatedAt')})")
                    return True
                else:
                    logger.warning(f"⚠️  MetafieldSet returned different metafield: {actual_namespace}.{actual_key} (expected {namespace}.{key})")
                    logger.warning(f"   Returned value: '{actual_value}'")
                    return False
            else:
                logger.error(f"❌ MetafieldSet returned no metafields in response for {namespace}.{key}")
                logger.debug(f"   Full metafieldsSet response: {json.dumps(metafields_set, indent=2)}")
                return False
        except Exception as e:
            logger.error(f"❌ Exception setting metafield {namespace}.{key} for variant {variant_gid}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    def sync_variant(self, product_gid: str, sku: str, price: str, barcode: str, mpn: Optional[str] = None) -> Optional[str]:
        """Updates pricing, enables 'Continue selling when out of stock', and sets both MPN metafields (Google / MPN and MPN)."""
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
                    "inventory_management": None, "inventory_policy": "continue"
                }}
                put_res = self.session.put(f"{self.rest_url}/variants/{v_id}.json", json=payload)
                put_res.raise_for_status()
                variant_gid = f"gid://shopify/ProductVariant/{v_id}"
                
                # Set MPN metafields if provided
                # Sets both "Google / MPN" and "MPN" 
                # Both use the same value from Pimcore's VendorPartNumber
                if mpn:
                    logger.info(f"Setting MPN metafields for variant {v_id} (GID: {variant_gid}) with value: {mpn}")
                    
                    # First, query ALL existing metafields to see what namespace/key combinations exist
                    logger.info(f"🔍 Checking existing metafields on variant to find correct namespace/key...")
                    all_metafields = self.get_variant_metafields(variant_gid)
                    
                    # Look for MPN-related metafields in the existing ones
                    mpn_metafield_info = None
                    google_mpn_metafield_info = None
                    for mf in all_metafields:
                        key_lower = mf.get('key', '').lower()
                        ns_lower = mf.get('namespace', '').lower()
                        if 'mpn' in key_lower:
                            if 'google' in ns_lower or 'google' in key_lower:
                                google_mpn_metafield_info = mf
                                logger.info(f"   ✓ Found Google MPN metafield: {mf.get('namespace')}.{mf.get('key')} = '{mf.get('value')}'")
                            else:
                                mpn_metafield_info = mf
                                logger.info(f"   ✓ Found MPN metafield: {mf.get('namespace')}.{mf.get('key')} = '{mf.get('value')}'")
                    
                    # Since this is a new variant, try to query an existing product/variant that already has MPN set
                    # The user mentioned 220 variants already have MPN, so let's find one of those
                    if not mpn_metafield_info:
                        logger.info(f"   No MPN metafield found on this new variant. Searching for an existing variant with MPN to detect namespace/key...")
                        try:
                            # Query for any product that might have MPN metafields
                            # We'll try to get a random product and check its variants
                            search_query = """
                            query {
                                products(first: 10) {
                                    edges {
                                        node {
                                            id
                                            variants(first: 5) {
                                                edges {
                                                    node {
                                                        id
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                            """
                            search_result = self.execute_graphql(search_query, {})
                            if "data" in search_result:
                                products = search_result["data"].get("products", {}).get("edges", [])
                                for product_edge in products:
                                    variants = product_edge.get("node", {}).get("variants", {}).get("edges", [])
                                    for variant_edge in variants:
                                        check_variant_gid = variant_edge.get("node", {}).get("id")
                                        if check_variant_gid and check_variant_gid != variant_gid:
                                            check_metafields = self.get_variant_metafields(check_variant_gid)
                                            for mf in check_metafields:
                                                key_lower = mf.get('key', '').lower()
                                                ns_lower = mf.get('namespace', '').lower()
                                                if 'mpn' in key_lower and 'google' not in ns_lower:
                                                    mpn_metafield_info = mf
                                                    logger.info(f"   ✓ Found existing MPN metafield on variant {check_variant_gid}: {mf.get('namespace')}.{mf.get('key')} = '{mf.get('value')}'")
                                                    break
                                            if mpn_metafield_info:
                                                break
                                    if mpn_metafield_info:
                                        break
                        except Exception as e:
                            logger.debug(f"   Could not search for existing variants: {e}")
                    
                    # Check if metafields already exist with our expected namespace/key
                    existing_google = self.get_variant_metafield(variant_gid, "mm-google-shopping", "mpn")
                    existing_mpn = self.get_variant_metafield(variant_gid, "custom", "vendor_part")
                    
                    # Set Google Shopping MPN metafield
                    google_success = self.set_variant_metafield(variant_gid, "mm-google-shopping", "mpn", mpn)
                    if not google_success:
                        logger.error(f"❌ Failed to set Google / MPN metafield")
                    
                    # Set standard MPN metafield
                    # Use the namespace/key we found, or default to custom.vendor_part (the actual MPN metafield key)
                    if mpn_metafield_info:
                        mpn_namespace = mpn_metafield_info.get('namespace')
                        mpn_key = mpn_metafield_info.get('key')
                        logger.info(f"   Using existing MPN metafield definition: {mpn_namespace}.{mpn_key}")
                    else:
                        # Use the correct namespace/key: custom.vendor_part (as shown in Shopify Admin)
                        mpn_namespace = "custom"
                        mpn_key = "vendor_part"
                        logger.info(f"   Using MPN metafield definition: {mpn_namespace}.{mpn_key} (as defined in Shopify)")
                    
                    mpn_success = self.set_variant_metafield(variant_gid, mpn_namespace, mpn_key, mpn)
                    if not mpn_success:
                        logger.error(f"❌ Failed to set MPN metafield ({mpn_namespace}.{mpn_key}) - check logs above for details")
                
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
# End of shopify_client.py — Version: 1.2.1
# ============================================================================
