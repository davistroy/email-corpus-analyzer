# Gmail Setup Guide

This guide covers setting up Gmail accounts with the Email Corpus Analyzer.

## Overview

Gmail integration requires OAuth 2.0 credentials from Google Cloud Console. This is a one-time setup process.

## Quick Setup

### Step 1: Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Note your project name

### Step 2: Enable Gmail API

1. In Google Cloud Console, go to **APIs & Services** > **Library**
2. Search for "Gmail API"
3. Click **Enable**

### Step 3: Configure OAuth Consent Screen

1. Go to **APIs & Services** > **OAuth consent screen**
2. Select **External** (unless you have Google Workspace)
3. Fill in the required fields:
   - App name: `Email Corpus Analyzer`
   - User support email: Your email
   - Developer contact: Your email
4. Click **Save and Continue**
5. On Scopes page, click **Add or Remove Scopes**
6. Find and select: `https://www.googleapis.com/auth/gmail.readonly`
7. Click **Save and Continue**
8. Add your email as a test user (required for External apps)
9. Click **Save and Continue**

### Step 4: Create OAuth Credentials

1. Go to **APIs & Services** > **Credentials**
2. Click **Create Credentials** > **OAuth client ID**
3. Application type: **Desktop app**
4. Name: `Email Corpus Analyzer`
5. Click **Create**
6. Click **Download JSON**
7. Save as `credentials.json` in a secure location

### Step 5: Add Mailbox

```bash
email-analyzer mailbox add \
  --name "Gmail" \
  --provider gmail \
  --email you@gmail.com \
  --credentials ~/path/to/credentials.json
```

### Step 6: Authenticate

```bash
email-analyzer mailbox auth Gmail
```

This opens your browser for Google OAuth consent:
1. Sign in with your Google account
2. Click **Continue** (if app is unverified warning appears)
3. Grant "View your email messages and settings" permission
4. Close the browser when complete

---

## Detailed Setup

### Google Cloud Console Setup

#### Creating a Project

1. Visit https://console.cloud.google.com/
2. Click the project dropdown at the top
3. Click **New Project**
4. Enter a project name (e.g., "Email Analyzer")
5. Click **Create**
6. Select your new project

#### Enabling the Gmail API

1. In the navigation menu, go to **APIs & Services** > **Library**
2. In the search box, type "Gmail"
3. Click **Gmail API**
4. Click the **Enable** button
5. Wait for the API to be enabled

#### OAuth Consent Screen Configuration

For personal Gmail accounts, you'll create an "External" app:

1. Go to **APIs & Services** > **OAuth consent screen**
2. Select **External** and click **Create**
3. Fill in App Information:
   - **App name**: `Email Corpus Analyzer`
   - **User support email**: Select your email
   - **App logo**: Optional
4. Under Developer contact information:
   - Add your email address
5. Click **Save and Continue**

On the Scopes page:
1. Click **Add or Remove Scopes**
2. In the filter, search for "gmail"
3. Check `https://www.googleapis.com/auth/gmail.readonly`
4. Click **Update**
5. Click **Save and Continue**

On the Test Users page:
1. Click **Add Users**
2. Enter the Gmail addresses you'll use
3. Click **Add**
4. Click **Save and Continue**

Review and go back to dashboard.

#### Creating OAuth Credentials

1. Go to **APIs & Services** > **Credentials**
2. Click **Create Credentials** at the top
3. Select **OAuth client ID**
4. For Application type, select **Desktop app**
5. Name: `Email Corpus Analyzer`
6. Click **Create**
7. A dialog shows your Client ID and Secret
8. Click **Download JSON**
9. Save the file as `credentials.json`

**Important**: Keep this file secure. It contains your OAuth credentials.

---

## Authentication Flow

When you run `email-analyzer mailbox auth Gmail`:

1. Your default browser opens to Google's sign-in page
2. Sign in with the Gmail account you want to analyze
3. If you see "Google hasn't verified this app":
   - Click **Advanced**
   - Click **Go to Email Corpus Analyzer (unsafe)**
   - This is normal for development/personal apps
4. Review the permissions requested
5. Click **Allow**
6. Browser shows "Authentication successful" - you can close it
7. The CLI confirms authentication is complete

### Required Permissions

The app requests:
- `gmail.readonly` - Read your email messages and settings

This is a **read-only** permission. The app cannot:
- Send emails
- Delete emails
- Modify emails

---

## Troubleshooting

### Error: "credentials.json not found"

Specify the full path to your credentials file:

```bash
email-analyzer mailbox add \
  --name "Gmail" \
  --provider gmail \
  --email you@gmail.com \
  --credentials /full/path/to/credentials.json
```

### Error: "Access blocked: App not verified"

For personal use, click through the warning:
1. Click **Advanced**
2. Click **Go to Email Corpus Analyzer (unsafe)**

For production use, submit your app for Google verification.

### Error: "User not in test users list"

Add your email to test users:
1. Go to Google Cloud Console
2. **APIs & Services** > **OAuth consent screen**
3. Click **Edit App**
4. Go to **Test users**
5. Add your Gmail address
6. Save

### Error: "OAuth2 credentials expired"

Re-authenticate:

```bash
email-analyzer mailbox auth Gmail
```

### Error: "API not enabled"

Enable the Gmail API:
1. Go to Google Cloud Console
2. **APIs & Services** > **Library**
3. Search "Gmail API"
4. Click **Enable**

### Error: "Rate limit exceeded"

Gmail API has quotas:
- 250 quota units per user per second
- 1,000,000 quota units per day

The Email Corpus Analyzer handles this with:
- Automatic retry with backoff
- Configurable batch sizes

Reduce batch size if needed:

```bash
email-analyzer extract --mailbox Gmail --batch-size 50
```

---

## Security Best Practices

### Protect credentials.json

```bash
# Secure file permissions
chmod 600 ~/credentials.json

# Store in secure location
mv ~/credentials.json ~/.email-analyzer/credentials/gmail-credentials.json
```

### Credential Storage

The Email Corpus Analyzer stores:
- `credentials.json` - Your OAuth client credentials (you provide)
- `token.json` - Your OAuth access/refresh tokens (auto-generated)

Both are stored in `~/.email-analyzer/credentials/` with secure permissions.

### Revoking Access

To remove the app's access to your Gmail:

1. Go to https://myaccount.google.com/permissions
2. Find "Email Corpus Analyzer"
3. Click **Remove Access**

Then remove local config:

```bash
email-analyzer mailbox remove Gmail --delete-data
```

---

## Google Workspace Accounts

For Google Workspace (formerly G Suite) accounts:

1. Your admin may need to allow the app
2. On OAuth consent screen, select **Internal** instead of **External**
3. No test user restrictions for internal apps

Contact your Google Workspace admin if you encounter access issues.

---

## Multiple Gmail Accounts

You can add multiple Gmail accounts:

```bash
# Personal account
email-analyzer mailbox add \
  --name "Personal Gmail" \
  --provider gmail \
  --email personal@gmail.com \
  --credentials ~/credentials.json

# Work account (same credentials file works)
email-analyzer mailbox add \
  --name "Work Gmail" \
  --provider gmail \
  --email work@company.com \
  --credentials ~/credentials.json
```

Each account requires separate authentication.

---

## API Documentation

For more information:
- [Gmail API Documentation](https://developers.google.com/gmail/api)
- [OAuth 2.0 for Desktop Apps](https://developers.google.com/identity/protocols/oauth2/native-app)
- [Gmail API Quotas](https://developers.google.com/gmail/api/reference/quota)
