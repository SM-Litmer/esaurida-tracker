import json
import asyncio
from playwright.async_api import async_playwright

TARGET_URLS = {
    "briquettes": "https://esaurida.lt/produktu-kategorija/biokuras/briketai/",
    "pellets": "https://esaurida.lt/produktu-kategorija/biokuras/granules/"
}

async def scrape_category(page, url):
    print(f"Scraping: {url}")
    # Go to URL and wait for network activity to settle
    await page.goto(url, wait_until="domcontentloaded", timeout=60000)
    
    # Wait specifically for the WooCommerce product loop grid to appear
    try:
        await page.wait_for_selector("ul.products, .product", timeout=10000)
    except Exception:
        print(f"Timeout waiting for products grid on {url}")

    # Scroll down to trigger any lazy loading
    await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
    await page.wait_for_timeout(1000)
    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    await page.wait_for_timeout(1500)

    products = await page.evaluate('''() => {
        const items = [];
        // Target standard WooCommerce product items
        const cardElements = document.querySelectorAll('ul.products li.product, div.product');
        
        cardElements.forEach(card => {
            // Find the title element specifically, bypassing badge spans
            const titleEl = card.querySelector('h2.woocommerce-loop-product__title, .woocommerce-loop-product__title, h2, h3');
            const priceEl = card.querySelector('.price');
            
            if (titleEl && priceEl) {
                let title = titleEl.innerText.trim();
                
                // Clean up title if promotional badges got mixed in
                if (title.includes('BE PABRANGIMO')) {
                    const parts = title.split('\\n');
                    // Get the last clean line which is usually the title
                    title = parts[parts.length - 1].trim();
                }

                const priceText = priceEl.innerText.trim().replace(/\\n/g, ' ');
                
                const insPrice = card.querySelector('ins .woocommerce-Price-amount');
                const delPrice = card.querySelector('del .woocommerce-Price-amount');
                
                if (title && title.length > 2) {
                    items.push({
                        title: title,
                        current_price: insPrice ? insPrice.innerText.trim() : priceText,
                        original_price: delPrice ? delPrice.innerText.trim() : null,
                        raw_price_string: priceText
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
        all_data = {}
        
        for category, url in TARGET_URLS.items():
            try:
                all_data[category] = await scrape_category(page, url)
            except Exception as e:
                print(f"Error scraping {category}: {e}")
                all_data[category] = []
                
        await browser.close()
        
        with open("prices.json", "w", encoding="utf-8") as f:
            json.dump(all_data, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    asyncio.run(main())
