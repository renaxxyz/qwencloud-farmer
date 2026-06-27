#!/usr/bin/env python3
"""
QwenCloud Auto-Register — automated account creation + API key harvester.
No Gmail OAuth needed — uses temp-mail.io disposable emails.

Based on: https://github.com/Vanszs/qwencloud-generator

Usage:
    python3 qwencloud_farmer.py              # single account
    python3 qwencloud_farmer.py -n 20        # batch 20 accounts
    python3 qwencloud_farmer.py -n 20 -o keys.txt  # custom output

Output: email|sk-ws-... per line
Base URL: https://dashscope-intl.aliyuncs.com/compatible-mode/v1
"""

import argparse
import json
import os
import random
import re
import sys
import time
import urllib.request
from pathlib import Path

# ── Bypass stale proxy env vars ──────────────────────────────────────
for k in list(os.environ):
    if "proxy" in k.lower():
        del os.environ[k]

from playwright.sync_api import sync_playwright  # noqa: E402

# ── Constants ─────────────────────────────────────────────────────────
TEMP_MAIL_API = "https://api.internal.temp-mail.io/api/v3"
QWEN_SIGNUP = "https://home.qwencloud.com/signup"
QWEN_REGISTER = "https://account.alibabacloud.com/sso/register"
QWEN_API_KEYS = "https://home.qwencloud.com/api-keys"
DASHSCOPE_BASE = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
DEFAULT_OUTPUT = "/tmp/qwencloud_keys.txt"

COUNTRIES = [
    "Afghanistan", "Albania", "Algeria", "Argentina", "Australia",
    "Austria", "Bahrain", "Bangladesh", "Belgium", "Brazil",
    "Cambodia", "Canada", "Chile", "Colombia", "Croatia",
    "Czech Republic", "Denmark", "Egypt", "Estonia", "Finland",
    "France", "Germany", "Greece", "Hong Kong(China)", "Hungary",
    "Iceland", "India", "Indonesia", "Ireland", "Israel",
    "Italy", "Japan", "Jordan", "Kazakhstan", "Kenya",
    "Korea", "Kuwait", "Laos", "Malaysia", "Mexico",
    "Morocco", "Nepal", "Netherlands", "New Zealand", "Nigeria",
    "Norway", "Oman", "Pakistan", "Peru", "Philippines",
    "Poland", "Portugal", "Qatar", "Romania", "Saudi Arabia",
    "Singapore", "South Africa", "Spain", "Sweden", "Switzerland",
    "Taiwan(China)", "Thailand", "Turkey", "Ukraine",
    "United Arab Emirates", "United Kingdom", "United States", "Vietnam",
]


# ── Temp Mail ─────────────────────────────────────────────────────────
def _opener():
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def get_temp_mail():
    req = urllib.request.Request(
        f"{TEMP_MAIL_API}/email/new",
        data=json.dumps({"min_name_length": 10, "max_name_length": 10}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    data = json.loads(_opener().open(req, timeout=15).read())
    return data["email"], data["token"]


def get_code(email, token, timeout=120):
    deadline = time.time() + timeout
    while time.time() < deadline:
        req = urllib.request.Request(
            f"{TEMP_MAIL_API}/email/{email}/messages",
            headers={"Authorization": f"Bearer {token}"},
        )
        try:
            msgs = json.loads(_opener().open(req, timeout=10).read())
        except Exception:
            time.sleep(3)
            continue
        for m in msgs:
            body = (m.get("body_text", "") or "") + (m.get("subject", "") or "")
            codes = re.findall(r"\b\d{6}\b", body)
            if codes:
                return codes[0]
        time.sleep(3)
    return None


# ── Core Flow ─────────────────────────────────────────────────────────
def _pick_country():
    return random.choice(COUNTRIES)


def register_one(headless=True, output_path=DEFAULT_OUTPUT):
    """Run a single signup flow. Returns dict with status/email/api_key."""
    email, token = get_temp_mail()
    country = _pick_country()
    print(f"📧 {email}  |  🌍 {country}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page()

        try:
            # 1 ─ open signup page
            page.goto(QWEN_SIGNUP, timeout=30000, wait_until="domcontentloaded")
            page.wait_for_timeout(2000)

            if "login" in page.url.lower():
                page.get_by_role("link", name="Sign Up").click()
                page.wait_for_timeout(3000)
            if "register" not in page.url.lower():
                page.goto(QWEN_REGISTER, timeout=15000)
                page.wait_for_timeout(2000)

            # 2 ─ fill email → Next
            page.get_by_role("textbox", name="Email").wait_for(state="visible", timeout=10000)
            page.get_by_role("textbox", name="Email").fill(email)
            page.wait_for_timeout(300)
            page.get_by_role("button", name="Next").click()
            page.wait_for_timeout(2000)

            # 3 ─ wait for verification code
            code = get_code(email, token, timeout=120)
            if not code:
                print(f"   ❌ No verification code")
                browser.close()
                return {"status": "error", "email": email, "reason": "no_code"}
            print(f"   🔑 Code: {code}")

            # 4 ─ enter OTP (all 6 digits into first input)
            otp = page.locator('input[type="text"]').first
            otp.wait_for(state="visible", timeout=10000)
            otp.press_sequentially(code)
            page.wait_for_timeout(2000)

            # 5 ─ country combobox (TYPE, don't click!)
            combo = page.locator('input[placeholder="Select your country/region"]')
            combo.wait_for(state="visible", timeout=10000)
            combo.click()
            page.wait_for_timeout(300)
            combo.fill(country)
            page.wait_for_timeout(500)
            page.locator(f'[role="option"]:has-text("{country}")').wait_for(
                state="visible", timeout=10000
            )
            page.locator(f'[role="option"]:has-text("{country}")').click()
            page.wait_for_timeout(300)

            # 6 ─ agree to terms (JS click for React)
            page.locator('input[type="checkbox"]').evaluate("el => el.click()")
            page.wait_for_timeout(300)

            # 7 ─ submit
            page.locator('button:has-text("Continue")').click()
            page.wait_for_timeout(5000)

            # 8 ─ dashboard → API keys
            if "home.qwencloud.com" not in page.url:
                print(f"   ❌ Dashboard not reached: {page.url[:80]}")
                browser.close()
                return {"status": "error", "email": email, "reason": "no_dashboard"}

            page.goto(QWEN_API_KEYS, timeout=15000, wait_until="domcontentloaded")
            page.wait_for_timeout(5000)

            if "login" in page.url.lower():
                print("   ⚠️ Session expired — account created, key skipped")
                browser.close()
                return {
                    "status": "partial",
                    "email": email,
                    "reason": "session_expired",
                }

            # dismiss mobile overlay
            try:
                close_btns = page.locator('button:has-text("Close")')
                if close_btns.count() > 0:
                    close_btns.first.click(timeout=3000)
                    page.wait_for_timeout(500)
            except Exception:
                pass

            # create API key
            page.locator('button:has-text("Create API key")').first.click(
                timeout=15000
            )
            page.wait_for_timeout(3000)

            # fill description
            try:
                page.locator('dialog input').first.wait_for(
                    state="visible", timeout=5000
                )
                page.locator("dialog input").first.fill("default")
            except Exception:
                page.get_by_role("textbox").last.fill("default")
            page.wait_for_timeout(500)

            # generate
            page.locator('button:has-text("Generate Key")').click(timeout=5000)
            page.wait_for_timeout(2000)

            # extract key
            api_key = None
            for inp in page.locator("input").all():
                try:
                    val = inp.input_value(timeout=2000)
                    if val and "sk-ws-" in val:
                        api_key = val
                        break
                except Exception:
                    pass
            if not api_key:
                api_key = page.locator("dialog input").first.input_value(timeout=10000)

            print(f"   ✅ API Key: {api_key[:50]}...")

            # save
            with open(output_path, "a") as f:
                f.write(f"{email}|{api_key}\n")

            browser.close()
            return {"status": "success", "email": email, "api_key": api_key}

        except Exception as e:
            print(f"   ❌ Error: {e}")
            browser.close()
            return {"status": "error", "email": email, "reason": str(e)[:80]}


def batch(count, headless=True, output_path=DEFAULT_OUTPUT):
    """Run N registrations, print summary."""
    results = []
    for i in range(count):
        print(f"\n── {i+1}/{count} " + "─" * 40)
        try:
            r = register_one(headless=headless, output_path=output_path)
            results.append(r)
        except Exception as e:
            print(f"   ❌ Fatal: {e}")
            results.append({"status": "fatal", "email": "?", "reason": str(e)[:80]})
        time.sleep(2)

    success = [r for r in results if r.get("status") == "success"]
    partial = [r for r in results if r.get("status") == "partial"]
    failed = [r for r in results if r.get("status") in ("error", "fatal")]

    print(f"\n{'='*55}")
    print(f"  ✅ {len(success)} success  |  ⚠️ {len(partial)} partial  |  ❌ {len(failed)} failed")
    print(f"{'='*55}")
    for r in success:
        print(f"  {r['email']}  →  {r['api_key'][:60]}...")
    print(f"\n  Saved to: {output_path}")


# ── CLI ───────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="QwenCloud Auto-Register — farm API keys with temp-mail.io"
    )
    parser.add_argument(
        "-n", "--count", type=int, default=1, help="Number of accounts (default: 1)"
    )
    parser.add_argument(
        "-o",
        "--output",
        default=DEFAULT_OUTPUT,
        help=f"Output file (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--headed", action="store_true", help="Show browser window (default: headless)"
    )
    args = parser.parse_args()

    if args.count == 1:
        register_one(headless=not args.headed, output_path=args.output)
    else:
        batch(args.count, headless=not args.headed, output_path=args.output)


if __name__ == "__main__":
    main()
