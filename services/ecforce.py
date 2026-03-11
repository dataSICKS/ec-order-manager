import os                                                                                                               
import requests 
from datetime import datetime, timedelta                                                                                


class EcforceClient:
      def __init__(self):
          self.base_url = os.environ.get("ECFORCE_BASE_URL", "").rstrip("/")
          self.token = os.environ.get("ECFORCE_API_TOKEN", "")
          self.headers = {
              "Authorization": f'Token token="{self.token}"',
              "Content-Type": "application/json",
              "Accept": "application/json",
          }
          proxy_url = os.environ.get("PROXY_URL", "")
          self.proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None

      def _get(self, endpoint, params=None):
          r = requests.get(f"{self.base_url}{endpoint}", headers=self.headers, params=params, proxies=self.proxies)
          r.raise_for_status()
          return r.json()

      def _post(self, endpoint, data=None):
          r = requests.post(f"{self.base_url}{endpoint}", headers=self.headers, json=data or {}, proxies=self.proxies)
          r.raise_for_status()
          return r.json()

      def _patch(self, endpoint, data):
          r = requests.patch(f"{self.base_url}{endpoint}", headers=self.headers, json=data, proxies=self.proxies)
          r.raise_for_status()
          return r.json()

      def _delete(self, endpoint):
          r = requests.delete(f"{self.base_url}{endpoint}", headers=self.headers, proxies=self.proxies)
          r.raise_for_status()
          return r.json()

      def _normalize(self, result):
          orders = []
          included = {f"{i['type']}_{i['id']}": i.get("attributes", {}) for i in result.get("included", [])}
          for item in result.get("data", []):
              attrs = dict(item.get("attributes", {}))
              attrs["id"] = item.get("id", str(attrs.get("id", "")))
              attrs["code"] = attrs.get("number", "")
              attrs["total_price"] = attrs.get("total", 0)
              rels = item.get("relationships", {})
              billing_id = (rels.get("billing_address", {}).get("data") or {}).get("id")
              billing = included.get(f"address_{billing_id}", {}) if billing_id else {}
              attrs["customer_last_name"] = billing.get("last_name", "")
              attrs["customer_first_name"] = billing.get("first_name", "")
              subs = (rels.get("subs_order", {}).get("data") or {})
              attrs["subscription_id"] = subs.get("id", "")
              items_data = rels.get("order_items", {}).get("data", [])
              attrs["line_items"] = [
                  included.get(f"order-item_{i['id']}", {"name": ""}) for i in items_data
              ]
              orders.append(attrs)
          return orders

      def get_address_error_orders(self):
          result = self._get("/orders.json", {
              "q[payment_status_eq]": "address_error",
              "per": 50,
              "include": "billing_address,order_items"
          })
          return self._normalize(result)

      def get_credit_failure_orders(self):
          result = self._get("/orders.json", {
              "q[payment_status_eq]": "authorization_error",
              "per": 50,
              "include": "billing_address"
          })
          return self._normalize(result)

      def get_test_orders(self):
          result = self._get("/orders.json", {
              "q[test_order_eq]": True,
              "q[state_not_eq]": "cancelled",
              "per": 50,
              "include": "billing_address,subs_order"
          })
          return self._normalize(result)

      def get_duplicate_orders(self):
          yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S")
          result = self._get("/orders.json", {
              "q[created_at_gteq]": yesterday,
              "q[state_not_eq]": "cancelled",
              "per": 200,
              "include": "billing_address,order_items"
          })
          orders = self._normalize(result)
          seen = {}
          duplicates = []
          for order in orders:
              customer_id = order.get("customer_id")
              items = order.get("line_items", [])
              product_key = tuple(sorted([str(item.get("variant_id", "")) for item in items]))
              key = (customer_id, product_key)
              if key in seen:
                  if seen[key] not in duplicates:
                      duplicates.append(seen[key])
                  duplicates.append(order)
              else:
                  seen[key] = order
          return duplicates

      def get_pending_shipment_orders(self):
          result = self._get("/orders.json", {
              "q[shipment_status_eq]": "pending",
              "q[state_eq]": "confirmed",
              "per": 200
          })
          return self._normalize(result)

      def get_dashboard_stats(self):
          try:
              return {
                  "address_errors": len(self.get_address_error_orders()),
                  "credit_failures": len(self.get_credit_failure_orders()),
                  "test_orders": len(self.get_test_orders()),
                  "duplicates": len(self.get_duplicate_orders()),
              }
          except Exception as e:
              return {"address_errors": 0, "credit_failures": 0, "test_orders": 0, "duplicates": 0, "error": str(e)}

      def cancel_payment(self, order_id):
          return self._post(f"/orders/{order_id}/payment_cancel.json")

      def re_authorize(self, order_id):
          return self._post(f"/orders/{order_id}/re_authorization.json")

      def update_address(self, order_id, address_data):
          return self._patch(f"/orders/{order_id}.json", {"order": {"shipping_address_attributes": address_data}})

      def add_inquiry_history(self, order_id, message):
          return self._post(f"/orders/{order_id}/inquiry_histories.json", {
              "inquiry_history": {"body": message}
          })

      def cancel_subscription(self, subscription_id):
          return self._patch(f"/subscriptions/{subscription_id}.json", {
              "subscription": {"status": "cancel"}
          })

      def delete_subscription(self, subscription_id):
          return self._delete(f"/subscriptions/{subscription_id}.json")

      def export_shipping_csv(self):
          r = requests.get(
              f"{self.base_url}/orders/export.csv",
              headers=self.headers,
              params={"format": "id2", "q[shipment_status_eq]": "pending"},
              proxies=self.proxies
          )
          r.raise_for_status()
          return r.content

      def mark_as_shipped(self, order_id, tracking_number, shipping_company):
          return self._patch(f"/orders/{order_id}.json", {
              "order": {
                  "shipment_status": "shipped",
                  "tracking_number": tracking_number,
                  "shipping_company": shipping_company,
              }
          })