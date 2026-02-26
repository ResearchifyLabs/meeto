import argparse

from playwright.sync_api import sync_playwright


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Playwright storage state for Google Meet login.")
    parser.add_argument("--output", default="storage_state.json", help="Output path for storage state JSON")
    parser.add_argument("--start-url", default="https://accounts.google.com/", help="Login start URL")
    args = parser.parse_args()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto(args.start_url)
        input("Log in to the Google account, then press Enter to save storage_state.json...")
        context.storage_state(path=args.output)
        browser.close()


if __name__ == "__main__":
    main()
