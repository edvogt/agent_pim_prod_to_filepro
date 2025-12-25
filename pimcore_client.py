# ============================================================================
#  pimcore_client.py — Pimcore API Handler
#  Version: 1.1.6
#  CHANGES: Removed ProductType field from GraphQL query (not in schema), added enhanced logging
# ============================================================================
import requests
import logging
import base64
import json
from typing import List, Optional
from pydantic import ValidationError
from models import PimcoreProduct

logger = logging.getLogger(__name__)

class PimcoreClient:
    def __init__(self, base_url: str, endpoint_name: str, api_key: str):
        self.api_url = f"{base_url}/pimcore-graphql-webservices/{endpoint_name}?apikey={api_key}"
        self.session = requests.Session()
        
        # Display API endpoint information (without exposing API key)
        api_url_display = self.api_url.split('?')[0]
        logger.info("=" * 80)
        logger.info("Pimcore API Configuration:")
        logger.info(f"  Base URL: {base_url}")
        logger.info(f"  Endpoint Name: {endpoint_name}")
        logger.info(f"  Full API URL: {api_url_display}")
        logger.info(f"  API Key: {'*' * min(len(api_key), 20)}... (hidden)")
        logger.info("=" * 80)
        
        # Test connectivity on initialization
        self.test_connectivity()
        # Note: list_available_fields() removed - can be called manually if needed

    def test_connectivity(self) -> bool:
        """
        Test API endpoint connectivity and authentication.
        Returns True if connection is successful, False otherwise.
        """
        logger.info("Testing Pimcore API connectivity...")
        
        # Simple test query to check if API is accessible
        test_query = """query {
          __schema {
            queryType {
              name
            }
          }
        }"""
        
        # Alternative: try a minimal product query
        simple_query = """query {
          getProdM06Listing(first: 1) {
            edges {
              node {
                id
                sku
              }
            }
          }
        }"""
        
        try:
            # Test 1: Check if endpoint is reachable
            logger.info(f"Testing endpoint: {self.api_url.split('?')[0]}")
            test_payload = {"query": simple_query}
            
            response = self.session.post(
                self.api_url, 
                json=test_payload,
                timeout=10
            )
            
            logger.info(f"API Response Status: {response.status_code}")
            logger.info(f"API Response Headers: {dict(response.headers)}")
            
            if response.status_code != 200:
                logger.error(f"❌ API returned non-200 status: {response.status_code}")
                logger.error(f"Response text: {response.text[:500]}")
                return False
            
            try:
                data = response.json()
            except ValueError as e:
                logger.error(f"❌ Invalid JSON response: {e}")
                logger.error(f"Response text: {response.text[:1000]}")
                return False
            
            # Check for GraphQL errors
            if "errors" in data:
                errors = data["errors"]
                logger.warning(f"⚠️  GraphQL errors in test query: {json.dumps(errors, indent=2)}")
                # Don't fail on errors - might just be schema differences
                
            # Check if we got data back
            if "data" in data:
                listing_data = data.get("data", {}).get("getProdM06Listing", {})
                edges = listing_data.get("edges", [])
                logger.info(f"✅ API connectivity confirmed - Test query returned {len(edges)} product(s)")
                
                if len(edges) > 0:
                    sample_node = edges[0].get("node", {})
                    logger.info(f"✅ Sample product retrieved: ID={sample_node.get('id')}, SKU={sample_node.get('sku')}")
                else:
                    logger.warning("⚠️  API is accessible but returned 0 products - products may not be published or accessible")
                
                return True
            else:
                logger.warning("⚠️  API responded but no 'data' field in response")
                logger.debug(f"Response structure: {list(data.keys())}")
                # Also list available queries to help diagnose
                self.list_available_queries()
                return True  # Still consider it connected
                
        except requests.exceptions.Timeout:
            logger.error("❌ API connection timeout - endpoint may be unreachable")
            return False
        except requests.exceptions.ConnectionError as e:
            logger.error(f"❌ API connection error - cannot reach endpoint: {e}")
            return False
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ API request error: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Unexpected error testing connectivity: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return False

    def list_available_fields(self) -> None:
        """
        Query GraphQL schema to list all available fields for the product type.
        This helps identify what fields are accessible via the API.
        """
        logger.info("Querying GraphQL schema for available fields...")
        
        # Query to get type information for the product object
        schema_query = """query {
          __type(name: "object_ProdM06") {
            name
            fields {
              name
              description
              type {
                name
                kind
                ofType {
                  name
                  kind
                }
              }
            }
          }
        }"""
        
        try:
            # Try to get the object type fields
            payload = {"query": schema_query}
            response = self.session.post(self.api_url, json=payload, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if "errors" in data:
                logger.warning(f"Schema query errors: {json.dumps(data['errors'], indent=2)}")
                logger.info("Trying to list all query types instead...")
                self.list_available_queries()
                return
            
            type_info = data.get("data", {}).get("__type")
            if type_info:
                fields = type_info.get("fields", [])
                logger.info(f"📋 Available fields for object_ProdM06 ({len(fields)} fields):")
                for field in sorted(fields, key=lambda x: x.get("name", "")):
                    field_name = field.get("name")
                    field_type = field.get("type", {})
                    type_name = field_type.get("name") or field_type.get("ofType", {}).get("name") or field_type.get("kind", "unknown")
                    description = field.get("description", "")
                    desc_text = f" ({description})" if description else ""
                    logger.info(f"  • {field_name}: {type_name}{desc_text}")
            else:
                logger.warning("No type information returned from schema query")
                logger.debug(f"Response data: {json.dumps(data, indent=2)[:1000]}")
                self.list_available_queries()
                
        except Exception as e:
            logger.error(f"Error querying schema: {e}")
            import traceback
            logger.debug(traceback.format_exc())

    def list_available_queries(self) -> None:
        """
        List all available queries in the GraphQL schema.
        """
        logger.info("Querying GraphQL schema for available queries...")
        
        query = """query {
          __schema {
            queryType {
              fields {
                name
                description
                args {
                  name
                  type {
                    name
                    kind
                  }
                }
              }
            }
          }
        }"""
        
        try:
            payload = {"query": query}
            response = self.session.post(self.api_url, json=payload, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if "errors" in data:
                logger.error(f"Query listing errors: {json.dumps(data['errors'], indent=2)}")
                return
            
            query_type = data.get("data", {}).get("__schema", {}).get("queryType")
            if query_type:
                fields = query_type.get("fields", [])
                logger.info(f"📋 Available queries ({len(fields)} queries):")
                for field in sorted(fields, key=lambda x: x.get("name", "")):
                    field_name = field.get("name")
                    args = field.get("args", [])
                    args_str = ", ".join([f"{arg.get('name')}: {arg.get('type', {}).get('name', 'unknown')}" for arg in args]) if args else "no args"
                    logger.info(f"  • {field_name}({args_str})")
            else:
                logger.warning("No query type information returned")
                
        except Exception as e:
            logger.error(f"Error listing queries: {e}")
            import traceback
            logger.debug(traceback.format_exc())

    def fetch_all_products(self, limit: int = 1000) -> List[PimcoreProduct]:
        """
        Fetch ALL products without any filtering - used for testing/debugging.
        Returns all products accessible via the API.
        """
        query = f"""query {{
          getProdM06Listing(first: {limit}) {{
            edges {{
              node {{
                id
                sku
                upc
                WebPrice
                MAP
                Retail
                BrandName
                Model
                VendorPartNumber
                Description_Short
                Description_Medium
                Specifications_WYSIWYG
                WhatsInBox
                PartPrefix
                ImagePrimary {{
                  id
                }}
              }}
            }}
          }}
        }}"""
        
        logger.info(f"Fetching ALL products (no filters) - limit: {limit}")
        
        try:
            payload = {"query": query}
            res = self.session.post(self.api_url, json=payload)
            res.raise_for_status()
            
            try:
                data = res.json()
            except ValueError as e:
                logger.error(f"Invalid JSON response: {e}")
                return []
            
            if "errors" in data:
                logger.error(f"GraphQL errors: {json.dumps(data['errors'], indent=2)}")
                return []
            
            listing_data = data.get("data", {}).get("getProdM06Listing", {})
            all_nodes = listing_data.get("edges", [])
            
            logger.info(f"✅ Fetched {len(all_nodes)} total products (no filters applied)")
            
            products = []
            for item in all_nodes:
                try:
                    node_data = item["node"].copy()
                    # Handle None values for optional string fields - convert to empty strings
                    if node_data.get("Description_Short") is None:
                        node_data["Description_Short"] = ""
                    if node_data.get("Description_Medium") is None:
                        node_data["Description_Medium"] = ""
                    if node_data.get("Specifications_WYSIWYG") is None:
                        node_data["Specifications_WYSIWYG"] = ""
                    if node_data.get("WhatsInBox") is None:
                        node_data["WhatsInBox"] = ""
                    if "ImagePrimary" in node_data and node_data.get("ImagePrimary"):
                        node_data["image_asset_id"] = node_data["ImagePrimary"].get("id")
                    else:
                        node_data["image_asset_id"] = None
                    products.append(PimcoreProduct(**node_data))
                except ValidationError as e:
                    logger.error(f"Validation error for product node: {e}")
                    continue
                except Exception as e:
                    logger.error(f"Error processing product node: {e}")
                    continue
            
            return products
            
        except requests.RequestException as e:
            logger.error(f"API request error: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return []

    def fetch_products(self, prefix: str, limit: int = 5) -> List[PimcoreProduct]:
        """
        Fetch products filtered by PartPrefix using exact match.
        Uses embedded filter string format: filter:"{\"PartPrefix\":\"VIZ\"}"
        Test confirmed this works - found 3 products with PartPrefix='VIZ'
        """
        logger.info(f"Fetching products for prefix '{prefix}'")
        
        # Use exact match filter (confirmed working - found 3 products with PartPrefix='VIZ')
        # Format: filter:"{\"PartPrefix\":\"VIZ\"}"
        filter_json = json.dumps({"PartPrefix": prefix}).replace('"', '\\"')
        
        query = f"""query {{
          getProdM06Listing(first: {limit}, filter: "{filter_json}") {{
            edges {{
              node {{
                id
                sku
                upc
                WebPrice
                MAP
                Retail
                BrandName
                Model
                VendorPartNumber
                Description_Short
                Description_Medium
                Specifications_WYSIWYG
                WhatsInBox
                PartPrefix
                ImagePrimary {{
                  id
                }}
              }}
            }}
          }}
        }}"""
        
        logger.info(f"Querying Pimcore API: {self.api_url.split('?')[0]}")
        logger.info(f"Using filter: PartPrefix='{prefix}' (exact match)")
        
        try:
            payload = {"query": query}
            res = self.session.post(self.api_url, json=payload)
            res.raise_for_status()
            
            try:
                data = res.json()
                # Log full response for debugging
                logger.debug(f"Full API response: {json.dumps(data, indent=2)[:1000]}")
            except ValueError as e:
                logger.error(f"Invalid JSON response from Pimcore: {e}")
                logger.error(f"Response status: {res.status_code}")
                logger.error(f"Response text: {res.text[:1000]}")
                return []
            
            # Check for GraphQL errors
            if "errors" in data:
                logger.error(f"GraphQL errors in response: {json.dumps(data['errors'], indent=2)}")
                return []
            
            # Log response structure
            logger.debug(f"Response keys: {list(data.keys())}")
            if "data" in data:
                logger.debug(f"Data keys: {list(data['data'].keys())}")
            
            # Extract nodes from response (already filtered by API)
            listing_data = data.get("data", {}).get("getProdM06Listing", {})
            nodes = listing_data.get("edges", [])
            
            logger.info(f"Found {len(nodes)} product(s) with PartPrefix='{prefix}' (exact match)")
            
            if len(nodes) == 0:
                logger.warning(f"No products found with PartPrefix='{prefix}' (exact match)")
                logger.info("Note: If PartPrefix contains '{prefix}' as substring, exact match won't work")
                logger.info("Example: PartPrefix='Playback, VizrtVIZ' won't match prefix='VIZ' with exact match")
            
            products = []
            
            for item in nodes:
                try:
                    node_data = item["node"].copy()
                    # Handle None values for optional string fields - convert to empty strings
                    if node_data.get("Description_Short") is None:
                        node_data["Description_Short"] = ""
                    if node_data.get("Description_Medium") is None:
                        node_data["Description_Medium"] = ""
                    if node_data.get("Specifications_WYSIWYG") is None:
                        node_data["Specifications_WYSIWYG"] = ""
                    if node_data.get("WhatsInBox") is None:
                        node_data["WhatsInBox"] = ""
                    # Extract ImagePrimary.id if it exists
                    if "ImagePrimary" in node_data and node_data.get("ImagePrimary"):
                        node_data["image_asset_id"] = node_data["ImagePrimary"].get("id")
                    else:
                        node_data["image_asset_id"] = None
                    products.append(PimcoreProduct(**node_data))
                except ValidationError as e:
                    logger.error(f"Validation error for product node (ID: {item.get('node', {}).get('id', 'unknown')}): {e}")
                    continue
                except Exception as e:
                    logger.error(f"Unexpected error processing product node: {e}")
                    continue
            
            return products
        except requests.RequestException as e:
            logger.error(f"Pimcore fetch error (HTTP): {e}")
            return []
        except Exception as e:
            logger.error(f"Pimcore fetch error: {e}")
            return []

    def fetch_products_no_filter(self, limit: int = 5) -> List[PimcoreProduct]:
        """Test method to fetch products without filter to see available fields."""
        query = """query($limit: Int) {
          getProdM06Listing(first: $limit) {
            edges { node { id sku upc WebPrice MAP Retail BrandName Model VendorPartNumber 
                           Description_Short Description_Medium Specifications_WYSIWYG WhatsInBox
                           ImagePrimary { id } } }
          }
        }"""
        logger.info(f"TEST QUERY: Fetching products without filter (limit: {limit})")
        logger.info(f"Querying Pimcore API: {self.api_url.split('?')[0]}")
        try:
            payload = {"query": query, "variables": {"limit": limit}}
            res = self.session.post(self.api_url, json=payload)
            res.raise_for_status()
            
            try:
                data = res.json()
            except ValueError as e:
                logger.error(f"Invalid JSON response from Pimcore: {e}")
                logger.error(f"Response text: {res.text[:500]}")
                return []
            
            if "errors" in data:
                logger.error(f"GraphQL errors in response: {data['errors']}")
                return []
            
            # Log the full response structure for debugging
            logger.info(f"Response data keys: {list(data.keys())}")
            if "data" in data:
                logger.info(f"Data keys: {list(data['data'].keys())}")
            
            listing_data = data.get("data", {}).get("getProdM06Listing", {})
            logger.info(f"TEST: getProdM06Listing structure keys: {list(listing_data.keys())}")
            
            # Check for totalCount or other metadata
            if "totalCount" in listing_data:
                logger.info(f"TEST: Total count in database: {listing_data.get('totalCount')}")
            if "pageInfo" in listing_data:
                logger.info(f"TEST: Page info: {listing_data.get('pageInfo')}")
            
            nodes = listing_data.get("edges", [])
            logger.info(f"TEST: Found {len(nodes)} product(s) without filter")
            
            # Log raw response structure for debugging empty results
            if len(nodes) == 0:
                logger.warning(f"TEST: No products found. Full listing_data: {listing_data}")
                logger.warning(f"TEST: Full response data: {data.get('data', {})}")
            
            # Log first product structure for inspection
            if nodes:
                first_node = nodes[0].get("node", {})
                logger.info(f"TEST: Sample product fields: {list(first_node.keys())}")
                logger.info(f"TEST: Sample product data: {first_node}")
            
            products = []
            for item in nodes:
                try:
                    node_data = item["node"].copy()
                    if "ImagePrimary" in node_data and node_data.get("ImagePrimary"):
                        node_data["image_asset_id"] = node_data["ImagePrimary"].get("id")
                    else:
                        node_data["image_asset_id"] = None
                    products.append(PimcoreProduct(**node_data))
                except ValidationError as e:
                    logger.error(f"Validation error for product node: {e}")
                    continue
                except Exception as e:
                    logger.error(f"Unexpected error processing product node: {e}")
                    continue
            
            return products
        except requests.RequestException as e:
            logger.error(f"Pimcore fetch error (HTTP): {e}")
            return []
        except Exception as e:
            logger.error(f"Pimcore fetch error: {e}")
            return []

    def get_asset_data(self, asset_id: str) -> Optional[bytes]:
        query = f"query {{ getAsset(id: {asset_id}) {{ data }} }}"
        try:
            res = self.session.post(self.api_url, json={"query": query})
            res.raise_for_status()  # Raise exception for 4xx/5xx status codes
            
            try:
                data = res.json()
            except ValueError as e:
                logger.error(f"Invalid JSON response for asset {asset_id}: {e}")
                return None
            
            b64 = data.get("data", {}).get("getAsset", {}).get("data")
            if b64:
                try:
                    return base64.b64decode(b64)
                except Exception as e:
                    logger.error(f"Base64 decode error for asset {asset_id}: {e}")
                    return None
            return None
        except requests.RequestException as e:
            logger.error(f"Asset download error (HTTP) for {asset_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Asset download error for {asset_id}: {e}")
            return None
# ============================================================================
# End of pimcore_client.py — Version: 1.1.6
# ============================================================================
