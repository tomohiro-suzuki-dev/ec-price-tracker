import asyncio
import json
import os
import re
from datetime import datetime
from pathlib import Path

import requests
import yaml
from playwright.async_api import async_playwright

RAKUTEN_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ja-JP,ja;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")
PRICES_FILE = Path("prices.json")

AMAZON_PRICE_SELECTORS = [
    "#corePriceDisplay_desktop_feature_div .a-price .a-offscreen",
    "#apex_desktop .a-price .a-offscreen",
    "#price_inside_buybox",
    "#priceblock_ourprice",
    "#priceblock_dealprice",
    ".a-price .a-offscreen",
]

RAKUTEN_PRICE_SELECTORS = [
    ".price--medium",
    ".price",
    ".item-price",
    "[class*='price']",
]


def extract_price_int(text: str):
    digits = re.sub(r"[^\d]", "", text)
    if digits and 100 <= int(digits) <= 100000:
        return int(digits)
    return None


async def get_price_amazon(page, url: str):
    await page.set_extra_http_headers({"Accept-Language": "ja-JP,ja;q=0.9"})
    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
    await page.wait_for_timeout(2000)

    for selector in AMAZON_PRICE_SELECTORS:
        try:
            elements = await page.query_selector_all(selector)
            for el in elements:
                price = extract_price_int(await el.inner_text())
                if price:
                    return price
        except Exception:
            continue
    return None


def get_price_rakuten_http(url: str):
    """requestsでHTMLのitemprop="price"から価格を取得する。"""
    try:
        resp = requests.get(url, headers=RAKUTEN_HEADERS, timeout=15)
        resp.raise_for_status()
        match = re.search(r'itemprop=["\']price["\'][^>]*content=["\'](\d+)["\']', resp.text)
        if not match:
            match = re.search(r'content=["\'](\d+)["\'][^>]*itemprop=["\']price["\']', resp.text)
        if match:
            return extract_price_int(match.group(1))
    except Exception as e:
        print(f"  Rakuten HTTP error: {e}")
    return None


async def get_price(page, site: str, url: str):
    if site == "Amazon":
        return await get_price_amazon(page, url)
    elif site == "楽天ブックス":
        return get_price_rakuten_http(url)
    return None


def send_discord_notification(product: str, site: str, url: str, prev: int, curr: int):
    if not DISCORD_WEBHOOK_URL:
        print("DISCORD_WEBHOOK_URL not set. Skipping notification.")
        return

    diff = curr - prev
    diff_pct = diff / prev * 100
    sign = "+" if diff > 0 else ""
    color = 0x2ECC71 if diff < 0 else 0xE74C3C  # 緑=値下がり 赤=値上がり
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    payload = {
        "embeds": [{
            "title": "価格変動を検知しました",
            "description": (
                f"**商品:** {product}\n"
                f"**サイト:** {site}\n"
                f"**前回価格:** ¥{prev:,}\n"
                f"**現在価格:** ¥{curr:,}\n"
                f"**変動:** {sign}¥{diff:,}（{sign}{diff_pct:.1f}%）\n"
                f"**URL:** {url}\n"
                f"**検知時刻:** {timestamp}"
            ),
            "color": color,
        }]
    }
    resp = requests.post(DISCORD_WEBHOOK_URL, json=payload)
    if resp.status_code not in (200, 204):
        print(f"Discord notification failed: {resp.status_code} {resp.text}")


async def main():
    with open("config.yml") as f:
        config = yaml.safe_load(f)

    previous_prices = {}
    if PRICES_FILE.exists():
        previous_prices = json.loads(PRICES_FILE.read_text())

    current_prices = {}

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
        )

        for product in config.get("products", []):
            name = product["name"]
            for entry in product.get("urls", []):
                site = entry["site"]
                url = entry["url"]
                key = f"{name}|{site}"
                print(f"Checking: {site} - {name}")

                try:
                    price = await get_price(page, site, url)
                except Exception as e:
                    print(f"Error: {e}")
                    continue

                if price is None:
                    print(f"  -> 価格取得失敗")
                    continue

                print(f"  -> ¥{price:,}")
                current_prices[key] = price

                if key in previous_prices:
                    if previous_prices[key] != price:
                        print(f"  -> 価格変動検知: ¥{previous_prices[key]:,} → ¥{price:,}")
                        send_discord_notification(name, site, url, previous_prices[key], price)
                    else:
                        print(f"  -> 変動なし")
                else:
                    print(f"  -> 初回実行（ベースライン保存）")

        await browser.close()

    PRICES_FILE.write_text(json.dumps(current_prices, indent=2, ensure_ascii=False))
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
