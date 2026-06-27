# QwenCloud Farmer 🚀

> Automated QwenCloud account registration + API key harvester using temp-mail.io and Playwright.

[![Stars](https://img.shields.io/github/stars/renaxxyz/qwencloud-farmer?style=social)](https://github.com/renaxxyz/qwencloud-farmer)

---

## ⚡ Quick Start

```bash
pip install playwright && playwright install chromium
wget https://raw.githubusercontent.com/renaxxyz/qwencloud-farmer/master/farmer.py
python3 farmer.py -n 20
```

## 🔧 Usage

```bash
# Single account
python3 farmer.py

# Batch 20 accounts → keys.txt
python3 farmer.py -n 20 -o keys.txt

# With visible browser (debug)
python3 farmer.py --headed
```

## 📦 Output Format

```
email@temp.com|sk-ws-H.xxxxxxxxxxxx
```

One key per line. Ready for bulk import into [9Router](https://github.com/nousresearch/9router) or any OpenAI-compatible proxy.

**Base URL:** `https://dashscope-intl.aliyuncs.com/compatible-mode/v1`

---

## 🧠 How It Works

| Step | Action |
|------|--------|
| 1 | Get disposable email from **temp-mail.io** API (no Gmail OAuth needed) |
| 2 | Navigate to QwenCloud signup via Playwright |
| 3 | Enter email → receive 6-digit OTP via temp-mail inbox |
| 4 | Type OTP via `press_sequentially` into verification inputs |
| 5 | **Country combobox:** CLICK then TYPE country name (it's a text input!) → select from filtered dropdown |
| 6 | JS-click agreement checkbox (required for React component) |
| 7 | Click Continue → dashboard reached |
| 8 | Navigate to `/api-keys` → Create API Key → extract `sk-ws-...` key |

### ⚠️ Critical Pitfall — Country Combobox

The country selector is a **text input with filtering**, NOT a pure click-select dropdown:

```python
# ✅ CORRECT
combo.click()          # open it
combo.fill("Canada")   # TYPE to filter
option.click()         # click the match

# ❌ WRONG
option.click()         # won't work — element not in DOM yet
```

---

## 📊 Expected Yield

| Batch Size | Success Rate | Keys Expected |
|------------|-------------|---------------|
| 10 | ~60-70% | 6-7 |
| 20 | ~60-70% | 12-14 |

~30-40% fail due to QwenCloud session expiry between registration and API key extraction. Accounts are still created — keys can be recovered by logging in manually.

---

## 🛠 Dependencies

- Python 3.11+
- [Playwright](https://playwright.dev/) (`pip install playwright && playwright install chromium`)

## 🌍 Credits

Based on [Vanszs/qwencloud-generator](https://github.com/Vanszs/qwencloud-generator) ★27  
Adapted from Gmail OAuth to temp-mail.io by [@renaxxyz](https://github.com/renaxxyz)

## 📄 Disclaimer

Educational and research purposes only. Respect QwenCloud's terms of service.
