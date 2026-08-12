import json
import asyncio
from playwright.async_api import async_playwright

MAIN_BIOKURAS_URL = "https://esaurida.lt/produktu-kategorija/biokuras/"

async def scrape_biokuras(page):
    print(f"Scraping main catalog: {MAIN_BIOKURAS_URL}")
    await page.goto(MAIN_BIOKURAS_URL, wait_until="domcontentloaded", timeout=60000)
    
    try:
        await page.wait_for_selector(".product", timeout=15000)
    except Exception as e:
        print(f"Selector timeout: {e}")

    # Scroll down to load all elements
    await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
    await page.wait_for_timeout(1000)
    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    await page.wait_for_timeout(2000)

    # Extract catalog items
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

async def get_product_details(page, url):
    """Visits the individual product page to extract exact weight or package info."""
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        
        # Extract specs from WooCommerce attribute tables or product descriptions
        details = await page.evaluate('''() => {
            const weightEl = document.querySelector('.product_meta, .woocommerce-product-attributes-item--weight .woocommerce-product-attributes-item__value, .shop_attributes');
            if (weightEl) {
                return weightEl.innerText.replace(/\\n/g, ' ').trim();
            }
            return null;
        }''')
        return details
    except Exception:
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
        
        all_items = await scrape_biokuras(page)
        
        briquettes = []
        pellets = []
        
        for item in all_items:
            title_lower = item["title"].lower()
            
            # Extract basic weight info from title if available
            weight_info = "Nenurodyta (Standartinė pakuotė/paletė)"
            if "didmaiš" in title_lower:
                weight_info = "Didmaišis (Big Bag ~1000 kg)"
            elif "15kg" in title_lower or "15 kg" in title_lower:
                weight_info = "15 kg maišai (Paletė ~960 kg)"
            elif "20l" in title_lower or "20 l" in title_lower:
                weight_info = "20L maišas"
            elif "40l" in title_lower or "40 l" in title_lower:
                weight_info = "40L maišas"

            enriched_item = {
                "title": item["title"],
                "price": item["price"],
                "weight_package": weight_info,
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
