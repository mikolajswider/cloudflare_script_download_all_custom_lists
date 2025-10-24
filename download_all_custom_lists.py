import requests
import os

# === CONFIGURATION ===
API_TOKEN = os.getenv("CLOUDFLARE_API_TOKEN")  # Recommended
ACCOUNT_ID = os.getenv("CLOUDFLARE_ACCOUNT_ID")  # or paste directly here

if not API_TOKEN or not ACCOUNT_ID:
    print("❌ Please set CLOUDFLARE_API_TOKEN and CLOUDFLARE_ACCOUNT_ID environment variables.")
    exit(1)

# === HEADERS ===
headers = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json"
}

# === STEP 1: Fetch all lists ===
lists_url = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/rules/lists"
resp = requests.get(lists_url, headers=headers)

if not resp.ok:
    print("❌ Failed to fetch lists:", resp.text)
    exit(1)

lists = resp.json().get("result", [])
print(f"✅ Found {len(lists)} lists")

os.makedirs("terraform_lists", exist_ok=True)

# === STEP 2: Fetch items for each list (with correct pagination) ===
for lst in lists:
    list_id = lst["id"]
    list_name = lst["name"]
    description = lst.get("description", "")
    kind = lst.get("kind", "ip")

    print(f"📄 Exporting {list_name} ({list_id})...")

    items_url = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/rules/lists/{list_id}/items"
    all_items = []
    cursor = None

    while True:
        params = {}
        if cursor:
            params["cursor"] = cursor
        items_resp = requests.get(items_url, headers=headers, params=params if cursor else None)
        if not items_resp.ok:
            print(f"⚠️ Failed to fetch items for {list_name}: {items_resp.text}")
            break

        data = items_resp.json()
        print(f"DEBUG: result_info = {data.get('result_info')}")
        page_items = data.get("result", [])
        print(f"DEBUG: Fetched {len(page_items)} items this page")
        all_items.extend(page_items)
        cursor = data.get("result_info", {}).get("cursors", {}).get("after")
        if not cursor:
            break

    print(f"  → {len(all_items)} items")

    # === Build Terraform resource ===
    tf_lines = [
        f'resource "cloudflare_list" "{list_name}" {{',
        f'  account_id  = "{ACCOUNT_ID}"',
        f'  name        = "{list_name}"',
        f'  kind        = "{kind}"',
        f'  description = "{description}"',
        ""
    ]

    for item in all_items:
        value = item.get("ip") or item.get("hostname") or item.get("value")
        comment = item.get("comment", "")
        if value:
            if comment:
                tf_lines.append(f'  item {{ value = "{value}" comment = "{comment}" }}')
            else:
                tf_lines.append(f'  item {{ value = "{value}" }}')

    tf_lines.append("}")
    tf_content = "\n".join(tf_lines)

    # === Write to file ===
    filename = f"terraform_lists/{list_name}.tf"
    with open(filename, "w") as f:
        f.write(tf_content)

    print(f"  ✅ Saved to {filename}")

print("\n🎉 Done! All lists exported to terraform_lists/*.tf")