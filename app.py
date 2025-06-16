from flask import Flask, render_template, request
import requests
from bs4 import BeautifulSoup
import os
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)

SCRAPER_API_KEY = '7446713b666c4444fbdd668de3ca63f2' 

def get_page_content(url):
    """Fetch page content using ScraperAPI with headers"""
    api_url = f'http://api.scraperapi.com?api_key={SCRAPER_API_KEY}&url={url}'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        response = requests.get(api_url, headers=headers, timeout=15)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"Error fetching {url}: {str(e)}")
        return None

def scrape_amazon(product_name):
    query = product_name.replace(" ", "+")
    url = f'https://www.amazon.in/s?k={query}'
    html = get_page_content(url)
    soup = BeautifulSoup(html, 'html.parser')

    try:
        name = soup.select('.a-color-base.a-text-normal')[0].get_text().strip()
        price = soup.select('.a-price-whole')[0].get_text().strip()
        return {"name": name, "price": price, "url": url}
    except:
        return {"error": "Product not found on Amazon"}

def scrape_flipkart(product_name):
    """Scrape Flipkart with updated selectors"""
    query = product_name.replace(" ", "%20")
    url = f"https://www.flipkart.com/search?q={query}"
    html = get_page_content(url)
    if not html:
        return {"error": "Failed to fetch Flipkart data"}

    soup = BeautifulSoup(html, 'html.parser')
    try:
        product = soup.select_one('div._1AtVbE')
        name = product.select_one('div._4rR01T').get_text().strip()
        price = product.select_one('div._30jeq3').get_text().strip()
        return {"name": name, "price": price, "url": url}
    except Exception as e:
        return {"error": f"Flipkart: {str(e)}"}

def scrape_croma(product_name):
    """Scrape Croma with error handling and updated selectors"""
    query = product_name.replace(" ", "+")
    url = f"https://www.croma.com/search/?text={query}"
    
    try:
        html = get_page_content(url)
        if not html:
            return {"error": "Failed to load Croma page"}
        
        soup = BeautifulSoup(html, 'html.parser')
        
        # Debug: Save HTML for inspection
        with open('croma_debug.html', 'w', encoding='utf-8') as f:
            f.write(soup.prettify())
        
        # Find product container - updated selector
        product = soup.find('div', {'class': 'product-list'}) or \
                 soup.find('ul', {'class': 'product-list'})
        
        if not product:
            return {"error": "Croma: Product grid not found"}
        
        # Get first product item - multiple possible selectors
        item = product.find('li', class_='product-item') or \
              product.find('div', class_='product-item') or \
              product.find('div', class_='cp-product')
        
        if not item:
            return {"error": "Croma: No products found"}
        
        # Product name with fallback selectors
        name = (item.find('h3', class_='product-title') or 
               item.find('a', class_='product-title') or
               item.find('h3')).get_text().strip()
        
        # Price with fallback selectors
        price_element = (item.find('span', class_='amount') or
                        item.find('span', class_='price') or
                        item.find('span', class_='new-price') or
                        item.find('div', class_='price'))
        
        if not price_element:
            return {"error": "Croma: Price element not found"}
        
        price = price_element.get_text().strip()
        
        # Clean price text
        price = ''.join(c for c in price if c.isdigit() or c in ['.', ','])
        if not price:
            return {"error": "Croma: Price format not recognized"}
        
        # Product URL
        product_url = url
        link = item.find('a', href=True)
        if link:
            product_url = "https://www.croma.com" + link['href'] if link['href'].startswith('/') else link['href']
        
        return {
            "name": name,
            "price": f"₹{price}",
            "url": product_url
        }
        
    except Exception as e:
        print(f"Croma scraping error: {str(e)}")
        return {"error": f"Croma: Technical error ({str(e)})"}

def scrape_ebay(product_name):
    """Scrape eBay India with robust selectors"""
    query = product_name.replace(" ", "+")
    url = f"https://www.ebay.com/sch/i.html?_nkw={query}"
    html = get_page_content(url)
    if not html:
        return {"error": "Failed to fetch eBay data"}

    soup = BeautifulSoup(html, 'html.parser')
    try:
        item = soup.select_one('li.s-item')
        name = item.select_one('.s-item__title').get_text().strip()
        price = item.select_one('.s-item__price').get_text().strip()
        return {"name": name, "price": price, "url": url}
    except Exception as e:
        return {"error": f"eBay: {str(e)}"}

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/compare')
def compare():
    product_name = request.args.get('product_name', '').strip()
    if not product_name:
        return render_template('index.html', data=None)

    with ThreadPoolExecutor() as executor:
        amazon = executor.submit(scrape_amazon, product_name)
        flipkart = executor.submit(scrape_flipkart, product_name)
        croma = executor.submit(scrape_croma, product_name)
        ebay = executor.submit(scrape_ebay, product_name)
        
        data = {
            "amazon": amazon.result(),
            "flipkart": flipkart.result(),
            "croma": croma.result(),
            "ebay": ebay.result()
        }

    return render_template('index.html', data=data, product_name=product_name)

if __name__ == '__main__':
    app.run(debug=True)