"""Capture screenshots of the running app for the user guide."""
import os
import time
import sys

sys.path.insert(0, '/Users/talgruenwald/.claude/skills/notebooklm/.venv/lib/python3.9/site-packages')

from patchright.sync_api import sync_playwright

OUT_DIR = "/Users/talgruenwald/projects/MedicalOpinion/docs/images"
os.makedirs(OUT_DIR, exist_ok=True)

URL = "http://127.0.0.1:5555"


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, channel="chrome")
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()
        page.goto(URL)
        page.wait_for_load_state("networkidle")
        time.sleep(3)

        # Use clicks (sidebar navigation) - works regardless of JS world isolation
        nav_items = page.locator(".sidebar-nav .nav-item")

        def goto_page(nav_index, name, scroll_top=True):
            nav_items.nth(nav_index).click()
            time.sleep(1)
            if scroll_top:
                page.mouse.wheel(0, -10000)
                time.sleep(0.3)
            page.screenshot(path=os.path.join(OUT_DIR, f"{name}.png"))
            print(f"  ✓ {name}.png")

        # 0=dashboard, 1=cases, 2=email-scan, 3=new-case, 4=settings
        goto_page(0, "01_dashboard")
        goto_page(1, "02_cases")

        # Click first row to view case detail
        page.locator("#cases-body tr").first.click()
        time.sleep(1)
        page.mouse.wheel(0, -10000)
        time.sleep(0.3)
        page.screenshot(path=os.path.join(OUT_DIR, "03_case_detail.png"))
        print("  ✓ 03_case_detail.png")

        # Click "edit" button (first ✎)
        edit_btns = page.locator("button[title='עריכה']")
        # We're in case detail now, find the edit button there
        page.locator("button:has-text('עריכת פרטים')").first.click()
        time.sleep(1)
        page.screenshot(path=os.path.join(OUT_DIR, "10_edit_modal.png"))
        print("  ✓ 10_edit_modal.png")

        # Close edit modal
        page.locator("#edit-modal .modal-close").click()
        time.sleep(0.5)

        goto_page(2, "05_email_scan")
        goto_page(3, "04_new_case")
        goto_page(4, "06_settings_top")

        # Scroll to email settings
        page.locator("input[name='email_address']").scroll_into_view_if_needed()
        time.sleep(0.5)
        page.screenshot(path=os.path.join(OUT_DIR, "07_settings_email.png"))
        print("  ✓ 07_settings_email.png")

        # Scroll to field manager
        page.locator("#field-manager-container").scroll_into_view_if_needed()
        time.sleep(0.5)
        page.screenshot(path=os.path.join(OUT_DIR, "08_field_manager.png"))
        print("  ✓ 08_field_manager.png")

        # Click "Add custom field" button
        page.locator("button:has-text('הוסף שדה חדש')").click()
        time.sleep(1)
        page.screenshot(path=os.path.join(OUT_DIR, "11_custom_field_modal.png"))
        print("  ✓ 11_custom_field_modal.png")

        # Close modal
        page.locator("#custom-field-modal .modal-close").click()
        time.sleep(0.5)

        # Scroll to update section
        page.locator("#current-version").scroll_into_view_if_needed()
        time.sleep(0.5)
        page.screenshot(path=os.path.join(OUT_DIR, "09_update.png"))
        print("  ✓ 09_update.png")

        browser.close()
    print(f"\n✅ Screenshots saved to: {OUT_DIR}")


if __name__ == "__main__":
    main()
