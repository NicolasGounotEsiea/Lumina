"""
PIPEDREAM — Étape 1 : Extraire les données du webhook LemonSqueezy
"""
import json


def handler(pd: "pipedream"):
    event = pd.steps["trigger"]["event"]
    body  = event.get("body", event)

    if isinstance(body, str):
        body = json.loads(body)

    # Ping de test LemonSqueezy ou event vide — on ignore
    if "meta" not in body:
        return {"skip": True, "reason": "ping de test ignoré"}

    event_name = body["meta"]["event_name"]

    if event_name != "order_created":
        return {"skip": True, "reason": f"event ignoré : {event_name}"}

    attrs = body["data"]["attributes"]
    item  = attrs.get("first_order_item", {})

    return {
        "skip":         False,
        "email":        attrs["user_email"].strip(),
        "name":         (attrs.get("user_name") or "Client").strip(),
        "product_name": item.get("product_name", "Lumina Control Pro"),
    }
