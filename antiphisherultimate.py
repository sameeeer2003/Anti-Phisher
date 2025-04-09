import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.edge.service import Service
from selenium.webdriver.edge.options import Options
from urllib.parse import urlparse

DUMMY_EMAIL = "**********"
DUMMY_PASSWORD = "*********"
CHECK_INTERVAL = 1
LEGITIMACY_INDICATORS = [
    "invalid", "incorrect", "wrong", "exist",
    "not found", "no account", "try again",
    "failed", "error", "unrecognized", "mismatch",
    "new", "create", "valid"
]

def show_notification(driver, message, is_warning=False):
    """Display notification after page stabilizes"""
    time.sleep(1)  
    notification_js = f"""
    // Remove existing notifications
    document.querySelectorAll('.phishguard-notification').forEach(el => el.remove());
    
    const notification = document.createElement('div');
    notification.className = 'phishguard-notification';
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 15px;
        border-radius: 5px;
        background-color: {"#ffebee" if is_warning else "#e8f5e9"};
        color: {"#d32f2f" if is_warning else "#2e7d32"};
        border: 1px solid {"#d32f2f" if is_warning else "#2e7d32"};
        z-index: 9999;
        box-shadow: 0 2px 10px rgba(0,0,0,0.2);
        max-width: 300px;
        font-family: Arial, sans-serif;
        transition: opacity 0.3s;
    `;
    
    notification.innerHTML = `
        <div style="margin-bottom:10px;">{message}</div>
        <button style="
            padding:5px 15px;
            background:{"#d32f2f" if is_warning else "#2e7d32"};
            color:white;
            border:none;
            border-radius:3px;
            cursor:pointer;
        ">OK</button>
    `;
    
    notification.querySelector('button').onclick = function() {{
        notification.style.opacity = '0';
        setTimeout(() => notification.remove(), 300);
    }};
    
    document.body.appendChild(notification);
    setTimeout(() => notification.style.opacity = '1', 10);
    setTimeout(() => {{
        notification.style.opacity = '0';
        setTimeout(() => notification.remove(), 300);
    }}, 10000);
    """
    driver.execute_script(notification_js)

class PageMemory:
    def __init__(self):
        self.tested_pages = set()
        self.phishing_domains = set()
        self.username_submitted = {}  
    
    def add_page(self, url):
        parsed = urlparse(url)
        self.tested_pages.add(f"{parsed.scheme}://{parsed.netloc}{parsed.path}")
    
    def has_page(self, url):
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}" in self.tested_pages
    
    def add_phishing(self, url):
        self.phishing_domains.add(urlparse(url).netloc)
    
    def mark_username_submitted(self, domain, username):
        self.username_submitted[domain] = username
    
    def was_username_submitted(self, domain, username):
        return self.username_submitted.get(domain) == username

def is_login_page(driver):
    """Detect login pages including single-field forms"""
    try:
        current_url = driver.current_url.lower()
        title = driver.title.lower()
        login_indicators = ["login", "signin", "auth", "account", "password"]
        
        if any(indicator in current_url for indicator in login_indicators):
            return True
        if any(indicator in title for indicator in login_indicators):
            return True
            
        if driver.find_elements(By.XPATH, "//form[.//input[@type='text' or @type='email']]"):
            return True
            
        if driver.find_elements(By.XPATH, "//input[@type='text' or @type='email'][contains(@name, 'user') or contains(@id, 'user') or contains(@name, 'mail') or contains(@id, 'mail')]"):
            return True
            
        return False
    except:
        return False

def check_legitimacy(driver):
    """Check for legitimacy indicators in page content"""
    try:
        page_text = driver.find_element(By.TAG_NAME, "body").text.lower()
        return any(indicator in page_text for indicator in LEGITIMACY_INDICATORS)
    except:
        return False

def handle_single_field_login(driver, page_memory):
    """Handle username/email-only login forms"""
    try:
        domain = urlparse(driver.current_url).netloc
        
        if page_memory.was_username_submitted(domain, DUMMY_EMAIL):
            return "already_submitted"
            
        username_field = driver.find_element(
            By.XPATH,
            "//input[@type='text' or @type='email' or contains(@name, 'user') or contains(@id, 'user') or contains(@name, 'mail') or contains(@id, 'mail')]"
        )
        
        username_field.send_keys(DUMMY_EMAIL)
        username_field.send_keys(Keys.RETURN)
        page_memory.mark_username_submitted(domain, DUMMY_EMAIL)
        
        time.sleep(1.5)  
        
        if driver.find_elements(By.XPATH, "//input[@type='password']"):
            return "password_page_shown"
            
        if check_legitimacy(driver):
            return "legitimate"
            
        return "unknown"
        
    except Exception as e:
        print(f"Single field login note: {str(e)}")
        return "error"

def test_login_page(driver, page_memory):
    """Test both single-field and traditional login forms"""
    try:
        original_url = driver.current_url
        original_domain = urlparse(original_url).netloc
        
        has_username_field = driver.find_elements(
            By.XPATH,
            "//input[@type='text' or @type='email'][contains(@name, 'user') or contains(@id, 'user') or contains(@name, 'mail') or contains(@id, 'mail')]"
        )
        
        has_password_field = driver.find_elements(By.XPATH, "//input[@type='password']")
        
        if has_username_field and not has_password_field:
            result = handle_single_field_login(driver, page_memory)
            
            if result == "password_page_shown":
                password_field = driver.find_element(By.XPATH, "//input[@type='password']")
                password_field.send_keys(DUMMY_PASSWORD)
                password_field.send_keys(Keys.RETURN)
                time.sleep(1.5)
                
            elif result == "legitimate":
                return "safe"
                
            elif result == "already_submitted":
                return "skip"
        
        elif has_username_field and has_password_field:
            username_field = driver.find_element(
                By.XPATH,
                "//input[@type='text' or @type='email' or contains(@name, 'user') or contains(@id, 'user') or contains(@name, 'mail') or contains(@id, 'mail')]"
            )
            password_field = driver.find_element(By.XPATH, "//input[@type='password']")
            
            username_field.send_keys(DUMMY_EMAIL)
            password_field.send_keys(DUMMY_PASSWORD)
            password_field.send_keys(Keys.RETURN)
            time.sleep(1.5)
        
        current_url = driver.current_url
        current_domain = urlparse(current_url).netloc
        
        if current_domain != original_domain:
            page_memory.add_phishing(current_url)
            return "phishing"
            
        if check_legitimacy(driver):
            return "safe"
            
        return "suspicious"
        
    except Exception as e:
        print(f"Login test note: {str(e)}")
        return "error"

def monitor_tabs(driver, page_memory):
    """Main monitoring loop with enhanced login detection"""
    while True:
        try:
            current_handles = driver.window_handles
            
            for handle in current_handles:
                try:
                    driver.switch_to.window(handle)
                    current_url = driver.current_url
                    
                    if (current_url in ["about:blank", "chrome://newtab/"] or 
                        urlparse(current_url).netloc in page_memory.phishing_domains):
                        continue
                    
                    if not page_memory.has_page(current_url) and is_login_page(driver):
                        print(f"🔍 Testing: {current_url}")
                        
                        result = test_login_page(driver, page_memory)
                        
                        if result == "skip":
                            continue
                            
                        page_memory.add_page(current_url)
                        driver.refresh()
                        
                        if result == "safe":
                            show_notification(driver, 
                                "✓ Verified legitimate login flow\n"
                                )
                        elif result == "suspicious":
                            show_notification(driver,
                                "⚠️ Suspicious login behavior\n"
                                ,
                                is_warning=True)
                        elif result == "phishing":
                            print(f"🚨 Phishing detected: {current_url}")
                        
                except Exception as e:
                    print(f"Tab monitoring note: {str(e)}")
                    continue
            
            time.sleep(CHECK_INTERVAL)
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Monitoring error: {str(e)}")
            time.sleep(1)

def main():
    page_memory = PageMemory()
    
    edge_options = Options()
    edge_options.add_argument("--guest")
    edge_options.add_argument("--disable-infobars")
    edge_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    
    service = Service(r"C:\Users\Adal\Desktop\antiphishing\msedgedriver.exe")
    driver = webdriver.Edge(service=service, options=edge_options)
    
    try:
        driver.get("about:blank")
        print("""
        Enhanced Phishing Detector
        -------------------------
        • Handles both single-field and traditional login forms
        • Tracks multi-step login flows
        • Press Ctrl+C to stop
        """)
        monitor_tabs(driver, page_memory)
    finally:
        driver.quit()

if __name__ == "__main__":
    main()