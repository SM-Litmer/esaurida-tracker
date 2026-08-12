import json
import asyncio
from playwright.async_api import async_playwright

TARGET_URLS = [
    "https://esaurida.lt/produktu-kategorija/biokuras/briketai/",
    "https://esaurida.lt/produktu-kategorija/biokuras/granules/"
]

async def scrape_category(page, url):
    await page.goto(url, wait_until="networkidle")
    
    products = await page.evaluate('''() => {
        const items = [];
        const cardElements = document.querySelectorAll('.product, .type-product');
        
        cardElements.forEach(card => {
            const titleEl = card.querySelector('.woocommerce-loop-product__title, .product-title, h2, h3');
            const priceEl = card.querySelector('.price');
            
            if (titleEl && priceEl) {
                const title = titleEl.innerText.trim();
                const priceText = priceEl.innerText.trim().replace(/\\n/g, ' ');
                
                const insPrice = card.querySelector('ins .woocommerce-Price-amount');
                const delPrice = card.querySelector('del .woocommerce-Price-amount');
                
                items.push({
                    title: title,
                    current_price: insPrice ? insPrice.innerText.trim() : priceText,
                    original_price: delPrice ? delPrice.innerText.trim() : null,
                    raw_price_string: priceText
                });
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
            locale="lt-LT"
        )
        
        page = await context.new_page()
        all_data = {}
        
        for url in TARGET_URLS:
            category = "briquettes" if "briketai" in url else "pellets"
            try:
                all_data[category] = await scrape_category(page, url)
            except Exception as e:
                all_data[category] = []
                
        await browser.close()
        
        with open("prices.json", "w", encoding="utf-8") as f:
            json.dump(all_data, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    asyncio.run(main())
