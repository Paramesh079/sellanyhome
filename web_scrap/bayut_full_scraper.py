import time
import re
import os
import pandas as pd
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup
from urllib.parse import urljoin

OUT_FILE = "bayut_all_locations_transactions.csv"
HEADER_WRITTEN = False
ROW_BUFFER = []

# ─── Flush buffer to CSV every N rows ────────────────────────────────

def flush_to_csv(force=False):
    global HEADER_WRITTEN, ROW_BUFFER
    if not ROW_BUFFER:
        return
    if len(ROW_BUFFER) < 20 and not force:
        return
    
    df = pd.DataFrame(ROW_BUFFER)
    if not HEADER_WRITTEN:
        df.to_csv(OUT_FILE, index=False, mode='w')
        HEADER_WRITTEN = True
    else:
        df.to_csv(OUT_FILE, index=False, mode='a', header=False)
    
    print(f"  💾 Wrote {len(ROW_BUFFER)} rows to CSV (total file rows: {sum(1 for _ in open(OUT_FILE)) - 1})")
    ROW_BUFFER = []

# ─── Table extraction (15-column layout) ─────────────────────────────

def extract_table_from_source(page_source, main_location, sub_location, building_project):
    soup = BeautifulSoup(page_source, 'html.parser')
    rows_added = 0
    
    for row in soup.find_all('tr'):
        date_div = row.find(attrs={'aria-label': 'Date'})
        if not date_div:
            continue
            
        date_text = " ".join(date_div.stripped_strings)
        
        loc_cell = row.find(attrs={'aria-label': 'Location'})
        category, sub_category, location_image, is_off_plan = '', '', '', False
        
        if loc_cell:
            text_container = loc_cell.find('div', class_=lambda c: c and '_07c05f81' in c)
            if not text_container:
                text_container = loc_cell.find('div')
            if text_container:
                lines = [child.text.strip() for child in text_container.children if child.text.strip()]
                if len(lines) == 1:
                    category = lines[0]
                elif len(lines) >= 2:
                    category = lines[0]
                    sub_category = " ".join(lines[1].split())
            img = loc_cell.find('img')
            if img and img.has_attr('src'):
                location_image = img['src']
            if 'off-plan' in loc_cell.text.lower():
                is_off_plan = True
                
        price, is_vacant = '', False
        price_cell = row.find('span', attrs={'aria-label': 'Price'})
        if price_cell:
            price_td = price_cell.find_parent('td')
            if price_td:
                price = price_cell.text.strip()
                if 'vacant' in price_td.text.lower():
                    is_vacant = True
        
        type_div = row.find(attrs={'aria-label': 'Type'})
        type_val = type_div.text.strip() if type_div else 'NA'
        if not type_val: type_val = 'NA'
        
        beds_div = row.find(attrs={'aria-label': 'Beds'})
        beds_val = beds_div.text.strip() if beds_div else 'NA'
        if beds_val == '-' or not beds_val: beds_val = 'NA'
        
        built_div = row.find(attrs={'aria-label': 'Build Up Area'})
        built_val = built_div.text.strip() if built_div else '-'
        if not built_val: built_val = '-'
        
        plot_div = row.find(attrs={'aria-label': 'Plot Area'})
        plot_val = plot_div.text.strip() if plot_div else '-'
        if not plot_val: plot_val = '-'
        
        ROW_BUFFER.append({
            'main_location': main_location,
            'sub_location': sub_location,
            'building_project': building_project,
            'location_selected': f"{main_location} > {sub_location} > {building_project}".strip(' > '),
            'date': date_text, 'category': category, 'sub-category': sub_category,
            'location_image': location_image, 'is_off_plan?': is_off_plan,
            'price(EAD)': price, 'is_Vacant_at_time_of_sale?': is_vacant,
            'type': type_val, 'beds': beds_val,
            'built_up(sqft)': built_val, 'plot(sqft)': plot_val
        })
        rows_added += 1
    
    # Flush every 20 rows
    flush_to_csv()
    return rows_added

# ─── Helpers ──────────────────────────────────────────────────────────

def click_view_all_locations(driver):
    return driver.execute_script("""
        let els = document.querySelectorAll('button, a, div[role="button"], span');
        for (let el of els) {
            let text = el.innerText || '';
            if (text.trim().toUpperCase() === 'VIEW ALL LOCATIONS') {
                el.scrollIntoView({block: 'center', behavior: 'instant'});
                el.click();
                return true;
            }
        }
        return false;
    """)

def ensure_last_12_months(driver):
    try:
        clicked = driver.execute_script("""
            let els = document.querySelectorAll('button, a, span, div');
            for (let el of els) {
                let t = el.innerText || '';
                if (t.trim().toLowerCase().includes('last') && t.trim().toLowerCase().includes('month')) {
                    el.click(); return true;
                }
            }
            return false;
        """)
        if clicked:
            time.sleep(2)
            driver.execute_script("""
                let els = document.querySelectorAll('button, a, span, div');
                for (let el of els) {
                    if ((el.innerText||'').trim() === 'Last 12 months') { el.click(); return; }
                }
            """)
            time.sleep(2)
    except:
        pass

def extract_location_links(driver):
    links_data = driver.execute_script("""
        let results = [];
        let anchors = document.querySelectorAll('a[href*="/property-market-analysis/transactions/sale/property/dubai/"]');
        for (let a of anchors) {
            results.push({url: a.getAttribute('href'), text: a.innerText.trim()});
        }
        return results;
    """)
    
    parsed, seen = [], set()
    for item in links_data:
        url = urljoin("https://www.bayut.com", item['url'])
        if url in seen: continue
        seen.add(url)
        text = item['text']
        count = 0
        matches = re.findall(r'\(([\d,]+)\)', text)
        if matches:
            try: count = int(matches[-1].replace(',', ''))
            except: pass
        name = text.replace(f"({matches[-1]})", "").strip() if matches else text.strip()
        name = " ".join(name.split())
        parsed.append({'url': url, 'name': name, 'count': count})
    
    parsed.sort(key=lambda x: x['count'])
    return parsed

# ─── Scrape all paginated pages ──────────────────────────────────────

def scrape_all_pages(driver, main_loc, sub_loc, building, indent=""):
    page = 1
    total = 0
    while True:
        print(f"{indent}  Page {page}...", end=" ")
        count = extract_table_from_source(driver.page_source, main_loc, sub_loc, building)
        print(f"{count} rows")
        total += count
        if count == 0:
            break
        try:
            nps = str(page + 1)
            btns = driver.find_elements(By.XPATH,
                f"//div[@title='Next']|//a[@title='Next']|//*[@aria-label='Next']|//*[text()='{nps}']")
            if btns:
                driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btns[-1])
                time.sleep(1)
                driver.execute_script("arguments[0].click();", btns[-1])
                time.sleep(5)
                page += 1
            else:
                break
        except:
            break
    return total

# ─── Recursive location scraper ──────────────────────────────────────

def scrape_location_recursive(driver, loc_url, loc_name, main_loc, sub_loc, building, depth=0):
    indent = "  " * depth
    print(f"{indent}→ {loc_name}")
    
    driver.get(loc_url)
    time.sleep(8)
    ensure_last_12_months(driver)
    
    has_sub = click_view_all_locations(driver)
    time.sleep(3)
    
    total_rows = 0
    
    if has_sub:
        sub_locs = extract_location_links(driver)
        sub_locs = [s for s in sub_locs if s['url'].rstrip('/') != loc_url.rstrip('/')]
        
        if sub_locs:
            print(f"{indent}  Found {len(sub_locs)} sub-locations (sorted lowest→highest)")
            for i, sub in enumerate(sub_locs):
                print(f"{indent}  [{i+1}/{len(sub_locs)}] {sub['name']} ({sub['count']})")
                
                # Determine hierarchy columns based on depth
                if depth == 0:
                    # We are at main location, sub is a district
                    rows = scrape_location_recursive(
                        driver, sub['url'], sub['name'],
                        main_loc=main_loc, sub_loc=sub['name'], building='',
                        depth=depth + 1
                    )
                elif depth == 1:
                    # We are at district level, sub is a building/project
                    rows = scrape_location_recursive(
                        driver, sub['url'], sub['name'],
                        main_loc=main_loc, sub_loc=sub_loc, building=sub['name'],
                        depth=depth + 1
                    )
                else:
                    # Even deeper? Just keep building name
                    rows = scrape_location_recursive(
                        driver, sub['url'], sub['name'],
                        main_loc=main_loc, sub_loc=sub_loc, building=sub['name'],
                        depth=depth + 1
                    )
                total_rows += rows
            return total_rows
    
    # No sub-locations → scrape table here
    driver.get(loc_url)
    time.sleep(6)
    ensure_last_12_months(driver)
    time.sleep(2)
    
    print(f"{indent}  Scraping: {main_loc} > {sub_loc} > {building}")
    total_rows = scrape_all_pages(driver, main_loc, sub_loc, building, indent)
    return total_rows

# ─── Main ─────────────────────────────────────────────────────────────

def scrape_bayut_all():
    global HEADER_WRITTEN, ROW_BUFFER
    HEADER_WRITTEN = False
    ROW_BUFFER = []
    
    # Remove old file if exists
    if os.path.exists(OUT_FILE):
        os.remove(OUT_FILE)
    
    print("Setting up Chrome...")
    options = uc.ChromeOptions()
    options.add_argument('--disable-popup-blocking')
    driver = uc.Chrome(options=options, version_main=145)
    
    base_url = "https://www.bayut.com/property-market-analysis/transactions/sale/property/"
    
    try:
        driver.get(base_url)
        print("Waiting 10s for initial load...")
        time.sleep(10)
        
        print("Clicking VIEW ALL LOCATIONS on main page...")
        if not click_view_all_locations(driver):
            print("ERROR: Could not find VIEW ALL LOCATIONS")
            return
        time.sleep(5)
        
        main_locations = extract_location_links(driver)
        print(f"\nFound {len(main_locations)} main locations (sorted lowest→highest):")
        for i, loc in enumerate(main_locations[:5]):
            print(f"  {i+1}. {loc['name']} ({loc['count']})")
        if len(main_locations) > 5:
            print(f"  ... and {len(main_locations) - 5} more\n")
        
        for idx, main_loc in enumerate(main_locations):
            print(f"\n{'='*60}")
            print(f"[{idx+1}/{len(main_locations)}] {main_loc['name']} ({main_loc['count']})")
            print(f"{'='*60}")
            
            rows = scrape_location_recursive(
                driver, main_loc['url'], main_loc['name'],
                main_loc=main_loc['name'], sub_loc='', building='',
                depth=0
            )
            
            # Flush any remaining rows after each main location
            flush_to_csv(force=True)
            print(f"✓ {rows} total rows for '{main_loc['name']}'")

    finally:
        # Flush anything remaining
        flush_to_csv(force=True)
        driver.quit()

    print(f"\n{'='*60}")
    print(f"DONE! All data saved to {OUT_FILE}")

if __name__ == "__main__":
    scrape_bayut_all()
