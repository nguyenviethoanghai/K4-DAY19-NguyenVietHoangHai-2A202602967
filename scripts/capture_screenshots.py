import time
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.edge.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def get_driver():
    options = Options()
    options.add_argument('--headless=new')
    options.add_argument('--window-size=1600,1000')
    driver = webdriver.Edge(options=options)
    driver.set_window_size(1600, 1000)
    return driver

def run_query(driver, cypher_text, wait_seconds=4):
    # Click on the editor
    editor = driver.find_element(By.CSS_SELECTOR, ".cm-content")
    editor.click()
    time.sleep(0.5)
    
    # Select all and delete
    editor.send_keys(Keys.CONTROL, "a")
    editor.send_keys(Keys.BACKSPACE)
    time.sleep(0.5)
    
    # Type the cypher query
    # To handle multiple lines or special characters cleanly:
    driver.execute_script("""
        const cm = document.querySelector('.cm-content');
        cm.focus();
    """)
    editor.send_keys(cypher_text)
    time.sleep(0.5)
    
    # Click the Run button or press Ctrl+Enter
    try:
        run_btn = driver.find_element(By.CSS_SELECTOR, "button[data-testid='run-button']")
        run_btn.click()
    except Exception:
        editor.send_keys(Keys.CONTROL, Keys.ENTER)
        
    time.sleep(wait_seconds)

def main():
    img_dir = Path("report/img")
    img_dir.mkdir(parents=True, exist_ok=True)
    
    driver = get_driver()
    driver.get("http://localhost:7474")
    time.sleep(5)
    
    # Check if login modal or password field is present
    try:
        pwds = driver.find_elements(By.CSS_SELECTOR, "input[name='password']")
        if pwds:
            pwds[0].send_keys("password123")
            time.sleep(0.5)
            submits = driver.find_elements(By.CSS_SELECTOR, "button[data-testid='connection-form-submit']")
            if submits:
                submits[0].click()
                time.sleep(5)
    except Exception as e:
        print("Login handling note:", e)

    # Also check if connection status is disconnected
    try:
        status_btn = driver.find_elements(By.CSS_SELECTOR, "button[data-testid='instance-menu-button']")
        if status_btn and "disconnected" in status_btn[0].text.lower():
            status_btn[0].click()
            time.sleep(2)
            pwds = driver.find_elements(By.CSS_SELECTOR, "input[name='password']")
            if pwds:
                pwds[0].send_keys("password123")
                submits = driver.find_elements(By.CSS_SELECTOR, "button[data-testid='connection-form-submit']")
                if submits:
                    submits[0].click()
                    time.sleep(5)
    except Exception as e:
        print("Connection status check note:", e)

    # Dismiss any onboarding popups/tooltips
    try:
        driver.execute_script("""
            document.querySelectorAll('button').forEach(b => {
                if (b.textContent.trim() === 'Dismiss' || b.textContent.includes('Dismiss')) {
                    b.click();
                }
            });
        """)
        time.sleep(1)
    except Exception as e:
        print("Dismiss note:", e)

    print("Executing :clear...")
    run_query(driver, ":clear", 1)

    # 1. Q-A: Count nodes
    print("Capturing Q-A: kg_count.png...")
    q_a = "MATCH (n) RETURN labels(n)[0] AS label, count(*) AS n ORDER BY n DESC;"
    run_query(driver, q_a, wait_seconds=5)
    # Ensure table view is selected if available
    try:
        table_tab = driver.find_elements(By.XPATH, "//button[contains(text(), 'Table') or @data-testid='table-view-tab']")
        if table_tab:
            table_tab[0].click()
            time.sleep(1)
    except Exception:
        pass
    driver.save_screenshot(str(img_dir / "kg_count.png"))
    print("Saved kg_count.png")

    # 2. Q-B: Cross-KB bridge
    print("Capturing Q-B: kg_cross_kb.png...")
    run_query(driver, ":clear", 1)
    q_b = "MATCH p=(:Person)-[:INVOLVED_IN]->(:Case)-[:CHARGED_WITH]->(:Crime)<-[:DEFINES]-(:Article) RETURN p LIMIT 25;"
    run_query(driver, q_b, wait_seconds=6)
    try:
        graph_tab = driver.find_elements(By.XPATH, "//button[contains(text(), 'Graph') or @data-testid='graph-view-tab']")
        if graph_tab:
            graph_tab[0].click()
            time.sleep(1)
    except Exception:
        pass
    driver.save_screenshot(str(img_dir / "kg_cross_kb.png"))
    print("Saved kg_cross_kb.png")

    # 3. Q-D: One case (Trần Thanh Tuấn)
    print("Capturing Q-D: kg_my_case.png...")
    run_query(driver, ":clear", 1)
    q_d = "MATCH p=(:Person {name:'Trần Thanh Tuấn'})-[:INVOLVED_IN]->(k:Case)-[:CHARGED_WITH]->(:Crime)<-[:DEFINES]-(:Article) OPTIONAL MATCH q=(k)-[:INVOLVES|LOCATED_IN]->() RETURN p, q;"
    run_query(driver, q_d, wait_seconds=6)
    try:
        graph_tab = driver.find_elements(By.XPATH, "//button[contains(text(), 'Graph') or @data-testid='graph-view-tab']")
        if graph_tab:
            graph_tab[0].click()
            time.sleep(1)
    except Exception:
        pass
    driver.save_screenshot(str(img_dir / "kg_my_case.png"))
    print("Saved kg_my_case.png")

    driver.quit()
    print("Done capturing screenshots!")

if __name__ == '__main__':
    main()
