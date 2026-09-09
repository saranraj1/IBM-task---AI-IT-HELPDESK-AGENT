import time
from pathlib import Path
from playwright.sync_api import sync_playwright

OUTPUT_DIR = Path("screenshots").resolve()
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def run():
    print("Starting Playwright screenshot capture...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Set a large, modern viewport for crisp report screenshots
        context = browser.new_context(viewport={"width": 1440, "height": 950})
        page = context.new_page()
        
        # 1. Load Main Dashboard
        print("1. Loading Dashboard...")
        page.goto("http://localhost:8501", wait_until="networkidle", timeout=45000)
        page.wait_for_timeout(4000)
        
        # Click "New Conversation" to ensure clean state
        try:
            new_conv_btn = page.locator("button:has-text('New Conversation')")
            if new_conv_btn.count() > 0:
                new_conv_btn.first.click()
                page.wait_for_timeout(2500)
        except Exception as e:
            print("New conv button notice:", e)

        # Capture 1: Main Dashboard
        p1 = OUTPUT_DIR / "fig1_command_center_dashboard.png"
        page.screenshot(path=str(p1), full_page=False)
        print(f"Captured: {p1}")

        # 2. Technical Query: "My WiFi is not connecting"
        print("2. Submitting Technical Query (WiFi)...")
        # Click the quick chip or type into chat
        wifi_chip = page.locator("button:has-text('WiFi Issues')")
        if wifi_chip.count() > 0:
            wifi_chip.first.click()
        else:
            chat_input = page.locator("textarea[data-testid='stChatInputTextArea']")
            chat_input.fill("My WiFi is not connecting")
            chat_input.press("Enter")

        # Wait for processing to finish (spinner disappears and assistant message appears)
        print("Waiting for response...")
        page.wait_for_timeout(7000)
        # Wait until no spinner
        page.wait_for_selector("[data-testid='stSpinner']", state="detached", timeout=25000)
        page.wait_for_timeout(2000)

        # Capture 2: Technical RAG Response
        p2 = OUTPUT_DIR / "fig2_technical_rag_response.png"
        page.screenshot(path=str(p2), full_page=False)
        print(f"Captured: {p2}")

        # 3. High Priority Ticket Query
        print("3. Submitting High-Priority Ticket Query...")
        chat_input = page.locator("textarea[data-testid='stChatInputTextArea']")
        chat_input.fill("Create a ticket because my laptop keeps restarting")
        chat_input.press("Enter")
        
        page.wait_for_timeout(6000)
        page.wait_for_selector("[data-testid='stSpinner']", state="detached", timeout=25000)
        page.wait_for_timeout(2000)

        # Capture 3: Human-in-the-Loop Confirmation Card with Priority Detection
        p3 = OUTPUT_DIR / "fig3_priority_detection_hitl.png"
        page.screenshot(path=str(p3), full_page=False)
        print(f"Captured: {p3}")

        # 4. Confirm Ticket Creation
        print("4. Confirming Ticket Creation (HITL YES)...")
        hitl_yes = page.locator("button:has-text('YES – Create Ticket')")
        if hitl_yes.count() > 0:
            hitl_yes.first.click()
            page.wait_for_timeout(5000)
            page.wait_for_selector("[data-testid='stSpinner']", state="detached", timeout=20000)
            page.wait_for_timeout(2000)

        # Capture 4: Created Ticket Card
        p4 = OUTPUT_DIR / "fig4_ticket_card_created.png"
        page.screenshot(path=str(p4), full_page=False)
        print(f"Captured: {p4}")

        # 5. List Tickets or Check Status
        print("5. Submitting List Tickets query...")
        chat_input = page.locator("textarea[data-testid='stChatInputTextArea']")
        chat_input.fill("List all open tickets")
        chat_input.press("Enter")
        page.wait_for_timeout(5000)
        page.wait_for_selector("[data-testid='stSpinner']", state="detached", timeout=20000)
        page.wait_for_timeout(2000)

        # Capture 5: Ticket Status & List Tool Execution
        p5 = OUTPUT_DIR / "fig5_ticket_management_query.png"
        page.screenshot(path=str(p5), full_page=False)
        print(f"Captured: {p5}")

        # 6. Sidebar Ticket Admin View
        print("6. Opening Ticket Admin Expander...")
        try:
            admin_expander = page.locator("summary:has-text('View & Close Open Tickets')")
            if admin_expander.count() > 0:
                admin_expander.first.click()
                page.wait_for_timeout(2000)
        except Exception as e:
            print("Expander notice:", e)

        # Capture 6: Sidebar Ticket Admin & Metric Counters
        p6 = OUTPUT_DIR / "fig6_sidebar_admin_metrics.png"
        page.screenshot(path=str(p6), full_page=False)
        print(f"Captured: {p6}")

        # 7. Long-Term Memory / Identity Test
        print("7. Testing Memory & Profile...")
        chat_input = page.locator("textarea[data-testid='stChatInputTextArea']")
        chat_input.fill("My name is Saran Raj and I am in the engineering department")
        chat_input.press("Enter")
        page.wait_for_timeout(5000)
        page.wait_for_selector("[data-testid='stSpinner']", state="detached", timeout=20000)
        page.wait_for_timeout(2000)

        # Capture 7: Profile Memory Learned Response
        p7 = OUTPUT_DIR / "fig7_user_profile_memory.png"
        page.screenshot(path=str(p7), full_page=False)
        print(f"Captured: {p7}")

        browser.close()
        print("All screenshots successfully captured!")

if __name__ == "__main__":
    run()
