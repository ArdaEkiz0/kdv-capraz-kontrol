<div align="center">

**[🇹🇷 Türkçe](README.md) · [🇬🇧 English](README_EN.md)**

# KDV Cross-Check (KDV Çapraz Kontrol)

**Automatically compare your e-Invoice, MAHSUP slip and Excel invoices against your KDV control ledger.**
Find differences, missing entries and errors in seconds.

[![Version](https://img.shields.io/github/v/release/ArdaEkiz0/kdv-capraz-kontrol?style=for-the-badge&label=version&color=7C3AED)](https://github.com/ArdaEkiz0/kdv-capraz-kontrol/releases/latest)
[![Downloads](https://img.shields.io/github/downloads/ArdaEkiz0/kdv-capraz-kontrol/total?style=for-the-badge&label=downloads&color=2563EB)](https://github.com/ArdaEkiz0/kdv-capraz-kontrol/releases)
[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Windows](https://img.shields.io/badge/Platform-Windows-0078D4?style=for-the-badge&logo=windows&logoColor=white)](https://microsoft.com)
[![License](https://img.shields.io/badge/License-MIT-16A34A?style=for-the-badge)](LICENSE)

</div>

---

## 📸 Screenshot

![KDV Cross-Check screenshot](screenshot.png)

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 📄 **Multiple Formats** | e-Invoice XML (UBL), e-Invoice/e-Archive PDF, MAHSUP slips, Excel invoice lists and scanned documents (OCR) |
| 🧾 **Zenom Ledger Support** | Zenom "MUAVİN RAPORU" reports read directly as a control ledger |
| 💼 **Luca / Türmob Support** | Luca "MUAVİN DEFTER" and slip exports read directly as a ledger; if integrator credentials are provided, the 191/391 ledger is fetched from Luca automatically |
| 👥 **Taxpayer Panel** | Switch between taxpayers; e-Archive purchase invoices are downloaded automatically from the Turkish Revenue Administration (GİB). Ledger files are remembered per period and auto-assigned on later runs. Passwords are stored only on your machine (DPAPI-encrypted) |
| ⚡ **GİB Fast Validation** | e-Archive REST API validates user code/password in seconds before downloading; the browser is never opened for empty periods |
| 🔍 **Smart Matching** | Cross-check by VKN + invoice number + amount; credit notes are split out automatically |
| 🧮 **KDV Rate Check** | Additionally verifies the invoice's KDV rate against the ledger totals (1% / 5% / 10% / 20%) |
| ✂️ **Withholding (Tevkifat) Support** | Compares withholding-recoded entries with the ledger on a rate basis |
| 📊 **Dashboard** | KPI cards, KDV distribution chart and monthly trend analysis |
| 🏪 **Vendor Summary** | Total base/KDT breakdown per vendor |
| 🧾 **Declaration Comparison** | Compares control results against the totals of two declaration periods |
| 📑 **Ba/Bs Form** | Generates the Muhtasar Ba/Bs form draft |
| 💾 **History Database** | Every run is stored automatically; compare against older runs |
| 🔎 **Advanced Filters** | Filter by date range, VKN, amount range and status |
| 📋 **Reports** | Detailed Excel and PDF reports |
| ✉️ **Email** | Send to your accountant in one click via Outlook or SMTP |
| 🖥️ **CLI Mode** | Run without the GUI for batch jobs (`cli.py`) |
| 🔄 **Auto-Update** | Checks for a new version on startup and updates with one click |

---

## 🚀 Quick Start

### One-Click (Recommended)

1. Download the latest release: [**Releases → Latest**](https://github.com/ArdaEkiz0/kdv-capraz-kontrol/releases/latest) → `kdv-kontrol-vX.X.X.zip` → extract to a folder
2. Double-click **`calistir.bat`** — that's it!

> `calistir.bat` will install Python automatically if needed, install all libraries and start the program. After the first run, a shortcut with the logo is created on your desktop.

### Manual Install (Alternative)

If Python 3.12+ is already installed:

```cmd
git clone https://github.com/ArdaEkiz0/kdv-capraz-kontrol.git
cd kdv-capraz-kontrol
py -3 -m pip install -r requirements.txt
calistir.bat
```

---

## 📖 Usage

### 1️⃣ Select Invoices
- **Select Invoice Files** → pick individual files (XML / PDF / Excel)
- **Select Invoice Folder** → load all invoices in a folder at once

### 2️⃣ Select the Ledger
- **Select Control Ledger** → select your KDV control ledger (.xlsx)
- Several ledger files can be selected together
- 💡 If you also select a sales ledger, MAHSUP slips are compared against the ledger

### 3️⃣ Run the Check
Results are listed instantly with color codes:

| Status | Color | Meaning |
|--------|-------|---------|
| **MATCHED** | 🟢 Green | Invoice ↔ ledger fully consistent |
| **WITHHOLDING** | 🔵 Blue | Consistent after withholding, matches the ledger |
| **DISCOUNTED** | 🔵 Blue | Calculated at the discounted rate |
| **AMOUNT MISMATCH** | 🔴 Red | Base/KDV amounts differ |
| **VKN MISMATCH** | 🔴 Red | Same invoice number, different VKN |
| **DUPLICATE** | 🔴 Red | Same invoice recorded twice |
| **NOT IN LEDGER** | 🔴 Red | Invoice not processed in the ledger |
| **NOT IN INVOICES** | 🔴 Red | Ledger record exists, no matching invoice |

### 4️⃣ Get the Report
- **Excel Report** / **PDF Report** → save a detailed report
- **Email** → send the report directly
- Double-click any row → document detail window; copy the invoice number with a single click

---

## 🔧 Advanced Tools

<details>
<summary><b>📊 Dashboard</b> — KPI cards, KDV distribution chart, monthly trend</summary>

Visually summarizes your control results; compare with past runs.
</details>

<details>
<summary><b>🧮 Rate Check</b> — KDV rate consistency audit</summary>

For every matched record, verifies the mathematical consistency between the invoice's KDV rate and the ledger amount. Catches invoices cut at the wrong rate.
</details>

<details>
<summary><b>🏪 Vendor Summary</b> — per-vendor breakdown</summary>

Total invoice count, base and KDV totals per VKN.
</details>

<details>
<summary><b>🧾 Declaration Comparison</b></summary>

Compares the totals of two declaration periods with your control results; shows KDV that did not reach the declaration.
</details>

<details>
<summary><b>📑 Muhtasar Ba/Bs Form</b></summary>

Generates a Ba/Bs form draft from the ledger data.
</details>

<details>
<summary><b>✉️ Email</b></summary>

Send the report in one click via Outlook or SMTP (Gmail: use an [App Password](https://myaccount.google.com/apppasswords)).
</details>

---

## 🖥️ CLI Mode

Use without the GUI, for batch jobs or scheduled tasks:

```cmd
py -3 cli.py --fatura C:\faturalar\ --cetvel C:\cetvel\kdv191.xlsx --cikti rapor.xlsx --donem 2026-07
```

| Argument | Description |
|----------|-------------|
| `--fatura` | Invoice file/folder paths (can be given multiple times) |
| `--cetvel` | Ledger file paths (can be given multiple times) |
| `--cikti` | Excel report output path (optional) |
| `--donem` | Filter to a specific period, e.g. `2026-07` |

---

## 🔄 Auto-Update

The program checks GitHub for the latest version on every start:

1. If a new version exists, an **Update** button appears in the top bar
2. Click it → read the release notes → **Download & Install**
3. The program updates itself and restarts — the desktop shortcut is preserved automatically

---

## 📜 Changelog

| Version | Highlights |
|---------|------------|
| **3.1.39** | Fixed empty Luca ledger export: now waits for report data to appear, exports the populated report, and retries once on empty output |
| **3.1.38** | Fixed empty results list; longer GİB fetch timeout + clear warning for empty categories |
| **3.1.37** | Falls back to sequential safe download when parallel e-invoice fetch from Luca fails |
| **3.1.36** | Parallel ZIP download from Luca (8 workers) — fixes the server rejection of the previous version |
| **3.1.35** | Fixed a hang on pages with 500+ invoices |

Full history: [Releases](https://github.com/ArdaEkiz0/kdv-capraz-kontrol/releases)

---

## ❓ FAQ

<details>
<summary><b>The program won't start?</b></summary>

Double-click `calistir.bat` again; missing components are installed automatically. If the problem persists, run the system check with `py -3 denetim.py`.
</details>

<details>
<summary><b>I get a "Python not found" error?</b></summary>

`calistir.bat` installs Python automatically. If you install it manually, tick **"Add python.exe to PATH"** during [Python 3.12](https://www.python.org/downloads/release/python-31210/) installation.
</details>

<details>
<summary><b>Are scanned (photo) invoices readable?</b></summary>

Yes — scanned PDF/image invoices are processed with OCR support ([Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) must be installed, with Turkish language data).
</details>

<details>
<summary><b>I loaded 500+ invoices and it got slower?</b></summary>

Use the **period filter** (a specific month instead of "All"). Optimized for 500+ invoices.
</details>

<details>
<summary><b>Turkish characters look garbled?</b></summary>

Make sure your system's region is set to **"Turkey"**.
</details>

---

## 📁 Project Structure

```
kdv-capraz-kontrol/
├── main.py                # Main application (GUI)
├── cli.py                 # Command line mode
├── matcher.py             # Cross-check engine
├── xml_oku.py             # UBL XML parsing
├── efatura.py             # E-Invoice/E-Archive PDF parsing
├── fis_listesi.py         # MAHSUP slip parsing
├── excel_oku.py           # Excel invoice/ledger reading
├── cetvel.py              # KDV ledger parsing
├── ocr.py                 # OCR support
├── iade_ayristirici.py    # Credit note splitting
├── oran_kontrol.py        # KDV rate consistency check
├── beyanname.py           # Declaration comparison
├── ozetler.py             # Vendor summary, KDV distribution, BA/Bs
├── report.py / report_pdf.py   # Excel / PDF report
├── dashboard.py           # Dashboard charts
├── db.py                  # Database (run history)
├── guncelleme.py          # Auto-update
├── denetim.py             # System check tool (py -3 denetim.py)
├── calistir.bat           # One-click install + run
└── logo.ico / logo.png    # Application logo
```

---

## 🛠️ Technical Details

Source formats:

| Source | Format | Description |
|--------|--------|-------------|
| e-Invoice | XML (UBL) | GİB-approved e-invoice format |
| E-Invoice | PDF | Single or multi-page |
| E-Archive | PDF | Individual invoices |
| MAHSUP Slip | PDF | Account-based records |
| Invoice List | Excel | VKN, base, KDV columns |
| KDV Ledger | Excel | Control ledger format |
| Sales Ledger | Excel | Account-based sales records |

**KDV calculation:** Base = KDV × 100 / rate · Total = Base + KDV · Rates: 1%, 5%, 10%, 20%

---

## 📞 Contact

| Platform | Link |
|----------|------|
| 🐙 **GitHub** | [@ArdaEkiz0](https://github.com/ArdaEkiz0) |
| 🔗 **LinkedIn** | [Arda M. Ekiz](https://www.linkedin.com/in/arda-mehmet-ekiz-107640333/) |
| 📷 **Instagram** | [@ardaaekiz](https://www.instagram.com/ardaaekiz/) |
| 📧 **Email** | ardaekiz72@gmail.com |

---

## ⚖️ License

[MIT License](LICENSE) © 2026 Arda M. Ekiz

---

<div align="center">

**Made with ❤️ by [Arda M. Ekiz](https://github.com/ArdaEkiz0)**

</div>