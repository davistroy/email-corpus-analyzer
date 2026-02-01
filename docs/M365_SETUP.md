# Email Source Setup Guide

This guide covers authentication setup for extracting emails from Hotmail/Outlook.com and Gmail.

## Hotmail / Outlook.com Setup

### How It Works

The extractor uses the **Microsoft Graph API** with **MSAL device code flow** — no Azure app registration needed. It authenticates via a well-known public client (Microsoft Graph Explorer) and calls `/me/messages`, which works with personal Hotmail, Outlook.com, and Live.com accounts.

### First-Time Authentication

```bash
python -m src.cli extract --user-email troy.davis@hotmail.com
```

On first run, you'll see:

```
============================================================
MICROSOFT AUTHENTICATION REQUIRED
============================================================
To sign in, use a web browser to open the page
https://microsoft.com/devicelogin and enter the code XXXXXXXX
============================================================
```

1. Open https://microsoft.com/devicelogin on any device
2. Enter the code shown
3. Sign in with your Microsoft account
4. Grant the `Mail.Read` permission when prompted
5. Return to the terminal — extraction begins automatically

### Token Caching

After first auth, tokens are cached at `~/.email-analyzer/ms_token_cache.json`. Subsequent runs use the cached token automatically — no re-authentication unless the token expires (typically after 90 days of inactivity).

To force re-authentication:
```bash
# Delete the token cache
rm ~/.email-analyzer/ms_token_cache.json

# Or use the standalone script with --force-auth
python scripts/fetch_emails_cli.py --force-auth --count 5
```

### Custom Azure App (Optional)

The default public client ID works for most cases. If you need a custom Azure app:

1. Go to https://portal.azure.com → App registrations → New registration
2. Name: "Email Corpus Analyzer" (or anything)
3. Supported account types: **Accounts in any organizational directory and personal Microsoft accounts**
4. Redirect URI: Select **Mobile and desktop applications** → `https://login.microsoftonline.com/common/oauth2/nativeclient`
5. API Permissions: Add **Mail.Read** (delegated) and **User.Read** (delegated)
6. Note the Application (client) ID

Then pass it when extracting:
```bash
# The --client-id flag is available on the standalone script
python scripts/fetch_emails_cli.py --count 500 --output ~/data/outputs/email_corpus.json
```

---

## Gmail Setup

### Prerequisites

Gmail extraction requires OAuth 2.0 client credentials from Google Cloud Console.

### Step 1: Create Google Cloud Project

1. Go to https://console.cloud.google.com/
2. Create a new project (or select existing)
3. Name it something like "Email Corpus Analyzer"

### Step 2: Enable Gmail API

1. Go to **APIs & Services** → **Library**
2. Search for "Gmail API"
3. Click **Enable**

### Step 3: Create OAuth Credentials

1. Go to **APIs & Services** → **Credentials**
2. Click **+ CREATE CREDENTIALS** → **OAuth client ID**
3. If prompted, configure the consent screen first:
   - User type: **External**
   - App name: "Email Corpus Analyzer"
   - Scopes: Add `gmail.readonly`
   - Test users: Add your Gmail address
4. Application type: **Desktop app**
5. Name: "Email Corpus Analyzer"
6. Click **Create**
7. Click **Download JSON** on the confirmation dialog

### Step 4: Save Credentials

Save the downloaded JSON file as:
```
~/.email-analyzer/gmail_credentials.json
```

On Windows:
```
C:\Users\YourName\.email-analyzer\gmail_credentials.json
```

### Step 5: First-Time Authentication

```bash
python -m src.cli extract --user-email your.email@gmail.com --source gmail
```

A browser window opens for Google sign-in:

1. Sign in with your Google account
2. Grant "View your email messages and settings" permission
3. The browser shows "Authentication successful" — return to terminal
4. Extraction begins

### Token Caching

Gmail tokens are cached at `~/.email-analyzer/gmail_token.json`. Refresh tokens persist until you revoke access in Google Account settings.

---

## Multi-Source Extraction

Extract from both Hotmail and Gmail into a single corpus:

```bash
python -m src.cli extract \
  --user-email troy.davis@hotmail.com \
  --source both \
  --gmail-email your.email@gmail.com
```

This runs both extractors sequentially and merges the results into one corpus file. The source is recorded in metadata as "Hotmail/M365+Gmail".

---

## Authentication Files

| File | Purpose | Created |
|------|---------|---------|
| `~/.email-analyzer/ms_token_cache.json` | Microsoft Graph OAuth tokens | First Hotmail extraction |
| `~/.email-analyzer/gmail_credentials.json` | Google OAuth client secrets | You download from Google Cloud Console |
| `~/.email-analyzer/gmail_token.json` | Google OAuth access/refresh tokens | First Gmail extraction |
| `~/.email-analyzer/config.yaml` | App configuration | Manual or `config init` |

All auth files are in your home directory and never committed to git.

---

## Troubleshooting

### "Authentication failed: Timeout"
The device code expires after 15 minutes. Run the command again to get a new code.

### "M365MCPClient.fetch_emails() called in stub mode"
You're running an old code path. The current extractor uses `GraphAPIClient` directly. Make sure you have the latest code.

### "Gmail credentials not found"
Download OAuth client JSON from Google Cloud Console and save to `~/.email-analyzer/gmail_credentials.json`.

### "Token refresh failed"
Delete the token cache and re-authenticate:
```bash
rm ~/.email-analyzer/ms_token_cache.json   # For Hotmail
rm ~/.email-analyzer/gmail_token.json       # For Gmail
```

### "Rate limited by Microsoft Graph API"
The extractor has automatic exponential backoff (up to 8 seconds). For very large mailboxes, use smaller batch sizes:
```bash
python -m src.cli extract --user-email you@hotmail.com --batch-size 100
```
