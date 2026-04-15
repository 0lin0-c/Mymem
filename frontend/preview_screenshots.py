from playwright.sync_api import sync_playwright

screenshots = []

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)

    pages_to_capture = [
        ('login.html', '登录页面'),
        ('index.html', '注册页面'),
        ('settings.html', '设置页面'),
        ('chat.html', '聊天页面'),
    ]

    for page_name, label in pages_to_capture:
        page = browser.new_page()
        page.set_viewport_size({"width": 390, "height": 844})  # iPhone 14 size
        page.goto(f'http://localhost:8080/{page_name}')
        page.wait_for_load_state('networkidle')

        screenshot_path = f'/tmp/{page_name.replace(".html", "")}_preview.png'
        page.screenshot(path=screenshot_path, full_page=False)
        screenshots.append((screenshot_path, label))
        print(f"Captured: {label} -> {screenshot_path}")
        page.close()

    browser.close()

print("\nAll screenshots captured!")
