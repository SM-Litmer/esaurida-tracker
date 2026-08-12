import json
import asyncio
from playwright.async_api import async_playwright

BIOKURA_URL = "https://esaurida.lt/produktu-kategorija/biokuras/"

async def scrape_all_biokuras(page):
    print(f"Scraping main page: {BIOKURA_URL}")
    await page.goto(BIOKURA_URL, wait_until="domcontentloaded", timeout=60000)
    
    # Wait for products grid
    try:
        await page.wait_for_selector(".product, li.type-product", timeout=15000)
    except Exception as e:
        print(f"Warning: Timeout waiting for selectors: {e}")

    # Scroll down to load all items
    await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
    await page.wait_for_timeout(1000)
    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    await page.wait_for_timeout(2000)

    products = await page.evaluate('''() => {
        const items = [];
        const cardElements = document.querySelectorAll('li.product, div.product');
        
        cardElements.forEach(card => {
            const titleEl = card.querySelector('.woocommerce-loop-product__title, h2.woocommerce-loop-product__title, h2, h3');
            const priceEl = card.querySelector('.price');
            
            if (titleEl && priceEl) {
                let titleText = titleEl.innerText.trim();
                
                // Clean up title if badge text got caught
                if (titleText.includes('BE PABRANGIMO')) {
                    const lines = titleText.split('\\n').map(l => l.trim()).filter(l => l.length > 0);
                    titleText = lines[lines.length - 1];
                }
                
                const insPrice = card.querySelector('ins .woocommerce-Price-amount');
                const delPrice = card.querySelector('del .woocommerce-Price-amount');
                const rawPrice = priceEl.innerText.trim().replace(/\\n/g, ' ');
                
                if (titleText && titleText.length > 2) {
                    items.push({
                        title: titleText,
                        current_price: insPrice ? insPrice.innerText.trim() : rawPrice,
                        original_price: delPrice ? delPrice.innerText.trim() : null,
                        raw_price_string: rawPrice
                    });
                }
            }
        });
        return items;
    }''')
    
    return products

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            locale="lt-LT",
            viewport={'width': 1440, 'height': 900}
        )
        
        page = await context.new_page()
        
        all_products = []
        try:
            all_products = await scrape_all_biokuras(page)
        except Exception as e:
            print(f"Error scraping: {e}")
            
        await browser.close()
        
        # Categorize products by keyword
        briquettes = [p for p in all_products if "briket" in p["title"].lower()]
        pellets = [p for p in all_products if "granul" in p["title"].lower()]
        
        structured_data = {
            "briquettes": briquettes,
            "pellets": pellets
        }
        
        with open("prices.json", "w", encoding="utf-8") as f:
            json.dump(structured_data, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    asyncio.run(main())
