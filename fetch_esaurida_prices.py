import json
import asyncio
import re
from playwright.async_api import async_playwright

MAIN_BIOKURAS_URL = "https://esaurida.lt/produktu-kategorija/biokuras/"

async def scrape_biokuras_catalog(page):
    print(f"Scraping catalog: {MAIN_BIOKURAS_URL}")
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

async def extract_exact_weight(page, url):
    """Visits the individual product URL and extracts exact weight details."""
    print(f"Fetching details from: {url}")
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=20000)
        
        weight = await page.evaluate('''() => {
            // Look for WooCommerce attribute table or specification text
            const attributeRows = document.querySelectorAll('tr.woocommerce-product-attributes-item');
            for (let row of attributeRows) {
                const label = row.querySelector('th');
                const value = row.querySelector('td');
                if (label && value && label.innerText.toLowerCase().includes('svoris')) {
                    return value.innerText.trim();
                }
            }
            
            // Fallback: look inside product meta or short description
            const meta = document.querySelector('.product_meta, .woocommerce-product-details__short-description');
            if (meta) {
                const text = meta.innerText;
                const match = text.match(/(\\d+\\s*(kg|t|g|m3|L))/i);
                if (match) return match[0];
            }
            return null;
        }''')
        return weight
    except Exception as e:
        print(f"Could not extract weight for {url}: {e}")
        return None

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
                # Visit the product page to get the exact weight attribute
                exact_weight = await extract_exact_weight(page, item["url"])
                
                # Default fallback if weight attribute isn't listed on eSaurida
                if not exact_weight:
                    if "didmaiš" in title_lower:
                        exact_weight = "~1000 kg (Didmaišis)"
                    elif "15kg" in title_lower or "15 kg" in title_lower:
                        exact_weight = "15 kg maišas / ~960 kg paletė"
                    else:
                        exact_weight = "~960 kg (Standartinė paletė)"

                enriched_item = {
                    "title": item["title"],
                    "price": item["price"],
                    "weight_package": exact_weight,
                    "url": item["url"]
                }
                
                if "briket" in title_lower:
                    briquettes.append(enriched_item)
                elif "granul" in title_lower:
                    pellets.append(enriched_item)
        
        await browser.close()
        
        output_data = {
            "briquettes": briquettes,
            "pellets": pellets
        }
        
        with open("prices.json", "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    asyncio.run(main())
