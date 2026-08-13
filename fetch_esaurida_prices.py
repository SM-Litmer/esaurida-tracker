import json
import asyncio
import re
from datetime import datetime, timezone
from playwright.async_api import async_playwright

MAIN_BIOKURAS_URL = "https://esaurida.lt/produktu-kategorija/biokuras/"

async def scrape_biokuras_catalog(page):
    print(f"Scraping main catalog: {MAIN_BIOKURAS_URL}")
    await page.goto(MAIN_BIOKURAS_URL, wait_until="domcontentloaded", timeout=60000)
    
    try:
        await page.wait_for_selector(".product", timeout=15000)
    except Exception as e:
        print(f"Selector timeout: {e}")

    await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
    await page.wait_for_timeout(1000)
    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    await page.wait_for_timeout(1500)

    items = await page.evaluate('''() => {
        const cardElements = document.querySelectorAll('li.product, div.product');
        const results = [];
        
        cardElements.forEach(card => {
            const titleEl = card.querySelector('.woocommerce-loop-product__title, h2.woocommerce-loop-product__title') || card.querySelector('a.woocommerce-LoopProduct-link h2');
            const priceEl = card.querySelector('.price');
            const linkEl = card.querySelector('a.woocommerce-LoopProduct-link') || card.querySelector('a');
            
            if (titleEl && priceEl && linkEl) {
                let rawTitle = titleEl.innerText.trim();
                
                if (rawTitle.includes('BE PABRANGIMO')) {
                    const lines = rawTitle.split('\\n').map(l => l.trim()).filter(l => l.length > 0 && !l.includes('BE PABRANGIMO') && !l.includes('atsiliepim'));
                    rawTitle = lines.length > 0 ? lines[lines.length - 1] : rawTitle;
                }
                
                const insPrice = card.querySelector('ins .woocommerce-Price-amount');
                let currentPrice = insPrice ? insPrice.innerText.trim() : priceEl.innerText.trim().replace(/\\n/g, ' ');
                
                if (currentPrice.includes('Current price is:')) {
                    const parts = currentPrice.split('Current price is:');
                    currentPrice = parts[parts.length - 1].trim();
                } else if (currentPrice.includes(' ')) {
                    const amounts = currentPrice.split(' ').filter(p => p.includes('€'));
                    if (amounts.length > 0) {
                        currentPrice = amounts[amounts.length - 1].trim();
                    }
                }

                if (rawTitle && rawTitle.length > 2) {
                    results.push({
                        title: rawTitle,
                        price: currentPrice,
                        url: linkEl.href
                    });
                }
            }
        });
        return results;
    }''')
    
    return items

async def extract_exact_details(page, url, title):
    """Visits the product page to extract exact weight and packaging format."""
    print(f"Fetching page details: {url}")
    title_lower = title.lower()
    
    # Default package classification
    package_type = "Paletė"
    if "didmaiš" in title_lower:
        package_type = "Didmaišis"
    elif "maišel" in title_lower or "15kg" in title_lower:
        package_type = "Maišeliai (15 kg) ant paletės"

    exact_weight = None

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=25000)
        
        # Scrape text from product description & attributes table
        page_text = await page.evaluate('''() => {
            const desc = document.querySelector('.woocommerce-product-details__short-description, .product_meta, #tab-description, .shop_attributes');
            return desc ? desc.innerText : document.body.innerText;
        }''')

        # 1. Look for explicit total weight patterns (e.g. "Bendras svoris 1050 kg", "1050kg", "960 kg")
        weight_matches = re.findall(r'(?:bendras svoris|svoris|paletėje|yra)\s*:?\s*(\d{3,4})\s*kg', page_text, re.IGNORECASE)
        if weight_matches:
            exact_weight = f"{weight_matches[0]} kg"
        else:
            # Look for general standalone kilogram values (e.g., "1050 kg", "960 kg", "800 kg")
            general_matches = re.findall(r'(\d{3,4})\s*kg', page_text, re.IGNORECASE)
            if general_matches:
                exact_weight = f"{general_matches[0]} kg"

    except Exception as e:
        print(f"Error fetching product page {url}: {e}")

    # Fallback to known site defaults if page parsing misses
    if not exact_weight:
        if "didmaiš" in title_lower:
            exact_weight = "1000 kg"
        elif "granul" in title_lower and "maišel" in title_lower:
            exact_weight = "1050 kg"
        else:
            exact_weight = "960 kg"

    return exact_weight, package_type

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            locale="lt-LT",
            viewport={'width': 1440, 'height': 900}
        )
        
        page = await context.new_page()
        all_items = await scrape_biokuras_catalog(page)
        
        briquettes = []
        pellets = []
        
        for item in all_items:
            title_lower = item["title"].lower()
            
            if "briket" in title_lower or "granul" in title_lower:
                weight, package = await extract_exact_details(page, item["url"], item["title"])

                enriched_item = {
                    "title": item["title"],
                    "price": item["price"],
                    "weight": weight,
                    "package": package,
                    "url": item["url"]
                }
                
                if "briket" in title_lower:
                    briquettes.append(enriched_item)
                elif "granul" in title_lower:
                    pellets.append(enriched_item)
        
        await browser.close()
        
        # Generate UTC ISO timestamp
        current_time_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        
        output_data = {
            "last_updated": current_time_iso,
            "briquettes": briquettes,
            "pellets": pellets
        }
        
        with open("prices.json", "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    asyncio.run(main())
