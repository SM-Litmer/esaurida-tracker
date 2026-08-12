import json
import asyncio
import re
from playwright.async_api import async_playwright

MAIN_BIOKURAS_URL = "https://esaurida.lt/produktu-kategorija/biokuras/"

async def scrape_biokuras(page):
    print(f"Scraping: {MAIN_BIOKURAS_URL}")
    await page.goto(MAIN_BIOKURAS_URL, wait_until="domcontentloaded", timeout=60000)
    
    try:
        await page.wait_for_selector(".product", timeout=15000)
    except Exception as e:
        print(f"Selector timeout: {e}")

    # Scroll down to ensure dynamic content renders
    await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
    await page.wait_for_timeout(1000)
    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    await page.wait_for_timeout(2000)

    products = await page.evaluate('''() => {
        const items = [];
        const cardElements = document.querySelectorAll('li.product, div.product');
        
        cardElements.forEach(card => {
            const titleEl = card.querySelector('.woocommerce-loop-product__title, h2.woocommerce-loop-product__title') || card.querySelector('a.woocommerce-LoopProduct-link h2');
            const priceEl = card.querySelector('.price');
            const linkEl = card.querySelector('a.woocommerce-LoopProduct-link') || card.querySelector('a');
            
            if (titleEl && priceEl) {
                let rawTitle = titleEl.innerText.trim();
                
                // Clean up badge artifacts from title
                if (rawTitle.includes('BE PABRANGIMO')) {
                    const lines = rawTitle.split('\\n').map(l => l.trim()).filter(l => l.length > 0 && !l.includes('BE PABRANGIMO') && !l.includes('atsiliepim'));
                    rawTitle = lines.length > 0 ? lines[lines.length - 1] : rawTitle;
                }
                
                // Get ONLY the current (discounted/final) price
                const insPrice = card.querySelector('ins .woocommerce-Price-amount');
                let currentPrice = insPrice ? insPrice.innerText.trim() : priceEl.innerText.trim().replace(/\\n/g, ' ');
                
                // If price container contains both prices separated by text, grab the last amount
                if (currentPrice.includes('Current price is:')) {
                    const parts = currentPrice.split('Current price is:');
                    currentPrice = parts[parts.length - 1].trim();
                } else if (currentPrice.includes(' ')) {
                    const amounts = currentPrice.split(' ').filter(p => p.includes('€'));
                    if (amounts.length > 0) {
                        currentPrice = amounts[amounts.length - 1].trim();
                    }
                }

                const productUrl = linkEl ? linkEl.href : null;

                if (rawTitle && rawTitle.length > 2) {
                    items.push({
                        title: rawTitle,
                        price: currentPrice,
                        url: productUrl
                    });
                }
            }
        });
        return items;
    }''')
    
    return products

def extract_package_info(title):
    """Parses weight/package descriptions from the product title."""
    title_lower = title.lower()
    
    if "didmaiš" in title_lower:
        return "Big Bag (Didmaišis) ~1000kg"
    elif "15kg" in title_lower or "15 kg" in title_lower:
        return "15 kg maišas / paletė"
    elif "20l" in title_lower or "20 l" in title_lower:
        return "20L pakuotė"
    elif "40l" in title_lower or "40 l" in title_lower:
        return "40L pakuotė"
    elif "1.96" in title_lower:
        return "1.96 m³ paletė"
    else:
        return "Standartinė paletė / pakuotė"

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            locale="lt-LT",
            viewport={'width': 1440, 'height': 900}
        )
        
        page = await context.new_page()
        
        all_items = []
        try:
            all_items = await scrape_biokuras(page)
        except Exception as e:
            print(f"Error executing scraper: {e}")
            
        await browser.close()
        
        # Categorize and enrich with package/weight details
        briquettes = []
        pellets = []
        
        for item in all_items:
            enriched_item = {
                "title": item["title"],
                "price": item["price"],
                "package_description": extract_package_info(item["title"]),
                "url": item["url"]
            }
            
            title_lower = item["title"].lower()
            if "briket" in title_lower:
                briquettes.append(enriched_item)
            elif "granul" in title_lower:
                pellets.append(enriched_item)
        
        output_data = {
            "briquettes": briquettes,
            "pellets": pellets
        }
        
        with open("prices.json", "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    asyncio.run(main())
