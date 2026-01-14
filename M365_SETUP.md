# Microsoft 365 Setup Guide

This guide covers setting up Microsoft 365 (Outlook, Hotmail, Live) email accounts with the Email Corpus Analyzer.

## Overview

The Email Corpus Analyzer supports two types of M365 accounts:
- **Personal accounts** (outlook.com, hotmail.com, live.com)
- **Corporate accounts** (work/school accounts with organization tenant)

## Quick Setup

### Personal Account (Outlook.com, Hotmail, Live)

For personal Microsoft accounts, no additional configuration is needed:

```bash
email-analyzer mailbox add \
  --name "Personal" \
  --provider m365 \
  --email you@outlook.com
```

Then authenticate:

```bash
email-analyzer mailbox auth Personal
```

This will display a device code. Open the URL shown and enter the code to authorize.

### Corporate Account

For work/school accounts, you need your organization's tenant ID and may need to register an app:

```bash
email-analyzer mailbox add \
  --name "Work" \
  --provider m365 \
  --email you@company.com \
  --tenant YOUR_TENANT_ID \
  --client-id YOUR_CLIENT_ID
```

---

## Authentication Flow

### Device Code Flow

The Email Corpus Analyzer uses the **device code flow** for authentication:

1. Run `email-analyzer mailbox auth <name>`
2. A device code is displayed (e.g., `ABCD1234`)
3. Open https://microsoft.com/devicelogin in your browser
4. Enter the device code
5. Sign in with your Microsoft account
6. Grant permissions when prompted
7. Close the browser - authentication complete

### Required Permissions

The application requests these permissions:
- `Mail.Read` - Read your mail
- `Mail.ReadBasic` - Read basic mail properties
- `User.Read` - Read your profile

These are **delegated permissions** (user-level), not application permissions.

---

## Corporate Account Setup

### Step 1: Get Tenant ID

Your tenant ID can be found in:
1. Azure Portal > Microsoft Entra ID > Overview
2. Or ask your IT administrator

Format: `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` (UUID)

### Step 2: Register an Application (if required)

If your organization requires app registration:

1. Go to [Azure Portal](https://portal.azure.com)
2. Navigate to **Microsoft Entra ID** > **App registrations**
3. Click **New registration**
4. Configure:
   - Name: `Email Corpus Analyzer`
   - Supported account types: `Accounts in this organizational directory only`
   - Redirect URI: `http://localhost` (Public client/native)
5. After creation, note the **Application (client) ID**
6. Go to **API permissions**
7. Add permissions:
   - Microsoft Graph > Delegated permissions
   - Select: `Mail.Read`, `Mail.ReadBasic`, `User.Read`
8. Click **Grant admin consent** (if you're an admin)

### Step 3: Add Mailbox

```bash
email-analyzer mailbox add \
  --name "Work" \
  --provider m365 \
  --email you@company.com \
  --tenant YOUR_TENANT_ID \
  --client-id YOUR_CLIENT_ID
```

### Step 4: Authenticate

```bash
email-analyzer mailbox auth Work
```

---

## Troubleshooting

### Error: "AADSTS50076: Need to consent to permissions"

Your admin needs to grant consent, or you need admin approval:

1. Contact your IT admin to grant consent
2. Or use an account with admin privileges

### Error: "AADSTS7000218: Invalid client_id"

The client ID is incorrect:
- Verify the client ID from Azure Portal
- Ensure no extra spaces or characters

### Error: "AADSTS90002: Tenant not found"

The tenant ID is incorrect:
- Verify the tenant ID from Azure Portal
- Format should be UUID: `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`

### Error: "Authentication timeout"

The device code expired (15 minutes):
- Run `email-analyzer mailbox auth <name>` again
- Complete authentication faster

### Error: "Access denied" or "Forbidden"

Insufficient permissions:
- Ensure `Mail.Read` permission is granted
- Contact your IT admin for permission approval

### Personal Account: "Tenant not supported"

Don't use `--tenant` for personal accounts:

```bash
# Wrong
email-analyzer mailbox add --name "Personal" --provider m365 \
  --email you@outlook.com --tenant common

# Correct
email-analyzer mailbox add --name "Personal" --provider m365 \
  --email you@outlook.com
```

---

## API Endpoints

The Email Corpus Analyzer uses:
- **Personal accounts**: `/me/messages` with delegated auth
- **Corporate accounts**: `/users/{email}/messages` or `/me/messages`

The correct endpoint is selected automatically based on your configuration.

---

## Rate Limits

Microsoft Graph API has rate limits:
- ~10,000 requests per 10 minutes per app
- ~120 requests per minute per user

The Email Corpus Analyzer handles rate limiting automatically with:
- Exponential backoff on 429 errors
- Configurable batch sizes
- Progress checkpointing

---

## Data Privacy

- All data is stored locally on your machine
- OAuth tokens are stored securely in `~/.email-analyzer/credentials/`
- No email content is transmitted to external services
- Tokens can be revoked at https://account.live.com/consent/Manage

---

## Re-authentication

If your token expires or you need to re-authenticate:

```bash
email-analyzer mailbox auth <name>
```

Tokens typically last 90 days for personal accounts.

---

## Removing Access

To remove the application's access to your email:

1. Go to https://account.live.com/consent/Manage (personal)
2. Or Azure Portal > Enterprise applications (corporate)
3. Find "Email Corpus Analyzer" and revoke access

Then remove the local configuration:

```bash
email-analyzer mailbox remove <name> --delete-data
```

---

## Support

For issues specific to M365 authentication:
1. Check Microsoft's [Graph API documentation](https://docs.microsoft.com/en-us/graph/api/resources/mail-api-overview)
2. Verify account permissions at https://portal.azure.com
3. Contact your IT administrator for corporate accounts
