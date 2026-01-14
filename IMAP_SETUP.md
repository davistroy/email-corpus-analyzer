# IMAP Setup Guide

This guide covers setting up IMAP email accounts with the Email Corpus Analyzer.

## Overview

IMAP (Internet Message Access Protocol) is a standard protocol supported by most email providers. Use this option when:
- Your provider isn't M365 or Gmail
- You prefer direct IMAP access
- You have a self-hosted email server

## Quick Setup

```bash
email-analyzer mailbox add \
  --name "Email" \
  --provider imap \
  --email you@example.com \
  --host imap.example.com \
  --port 993
```

You'll be prompted for your password securely.

Then authenticate (verifies connection):

```bash
email-analyzer mailbox auth Email
```

---

## Common IMAP Servers

| Provider | IMAP Server | Port |
|----------|-------------|------|
| Yahoo Mail | imap.mail.yahoo.com | 993 |
| AOL | imap.aol.com | 993 |
| iCloud | imap.mail.me.com | 993 |
| Zoho Mail | imap.zoho.com | 993 |
| ProtonMail | 127.0.0.1 (via Bridge) | 1143 |
| Fastmail | imap.fastmail.com | 993 |
| GMX | imap.gmx.com | 993 |
| Mail.com | imap.mail.com | 993 |
| Yandex | imap.yandex.com | 993 |

---

## Setup Examples

### Yahoo Mail

```bash
email-analyzer mailbox add \
  --name "Yahoo" \
  --provider imap \
  --email you@yahoo.com \
  --host imap.mail.yahoo.com \
  --port 993
```

**Note**: Yahoo requires an App Password. See [Yahoo App Passwords](#yahoo-mail-setup).

### iCloud Mail

```bash
email-analyzer mailbox add \
  --name "iCloud" \
  --provider imap \
  --email you@icloud.com \
  --host imap.mail.me.com \
  --port 993
```

**Note**: iCloud requires an App-Specific Password. See [iCloud Setup](#icloud-setup).

### ProtonMail (via Bridge)

```bash
# Start ProtonMail Bridge first
email-analyzer mailbox add \
  --name "ProtonMail" \
  --provider imap \
  --email you@protonmail.com \
  --host 127.0.0.1 \
  --port 1143
```

### Self-Hosted (Dovecot, etc.)

```bash
email-analyzer mailbox add \
  --name "Server" \
  --provider imap \
  --email you@yourdomain.com \
  --host mail.yourdomain.com \
  --port 993
```

---

## Authentication

### Password Authentication

When adding a mailbox, you'll be prompted for your password:

```bash
$ email-analyzer mailbox add --name "Email" --provider imap \
    --email you@example.com --host imap.example.com
IMAP password: ********
```

Or provide it directly (not recommended for security):

```bash
email-analyzer mailbox add \
  --name "Email" \
  --provider imap \
  --email you@example.com \
  --host imap.example.com \
  --password "your-password"
```

### App Passwords

Many providers require "App Passwords" instead of your regular password when using third-party apps. This is more secure as:
- App passwords can be revoked individually
- They don't expose your main password
- Some providers require them when 2FA is enabled

---

## Provider-Specific Setup

### Yahoo Mail Setup

Yahoo requires an App Password:

1. Go to https://login.yahoo.com/account/security
2. Sign in to your Yahoo account
3. Click **Generate app password**
4. Select **Other App** and name it "Email Corpus Analyzer"
5. Copy the generated password
6. Use this password (not your Yahoo password) when adding the mailbox

```bash
email-analyzer mailbox add \
  --name "Yahoo" \
  --provider imap \
  --email you@yahoo.com \
  --host imap.mail.yahoo.com \
  --port 993
# Enter the App Password when prompted
```

### iCloud Setup

iCloud requires an App-Specific Password:

1. Go to https://appleid.apple.com/
2. Sign in with your Apple ID
3. In the Security section, click **App-Specific Passwords**
4. Click **Generate an app-specific password**
5. Name it "Email Corpus Analyzer"
6. Copy the generated password

```bash
email-analyzer mailbox add \
  --name "iCloud" \
  --provider imap \
  --email you@icloud.com \
  --host imap.mail.me.com \
  --port 993
# Enter the App-Specific Password when prompted
```

### ProtonMail Setup

ProtonMail requires the ProtonMail Bridge application:

1. Download and install [ProtonMail Bridge](https://protonmail.com/bridge/)
2. Sign in to the Bridge with your ProtonMail account
3. The Bridge shows IMAP settings:
   - Host: `127.0.0.1`
   - Port: `1143`
   - Password: (shown in Bridge)

```bash
email-analyzer mailbox add \
  --name "ProtonMail" \
  --provider imap \
  --email you@protonmail.com \
  --host 127.0.0.1 \
  --port 1143
# Use the password shown in ProtonMail Bridge
```

### Zoho Mail Setup

Zoho Mail works with your regular password if IMAP is enabled:

1. Log in to Zoho Mail
2. Go to Settings > Mail Accounts
3. Enable IMAP access

```bash
email-analyzer mailbox add \
  --name "Zoho" \
  --provider imap \
  --email you@zoho.com \
  --host imap.zoho.com \
  --port 993
```

---

## SSL/TLS Configuration

### Default (SSL/TLS on port 993)

Most modern servers use implicit SSL on port 993:

```bash
email-analyzer mailbox add \
  --name "Email" \
  --provider imap \
  --email you@example.com \
  --host imap.example.com \
  --port 993
```

### STARTTLS (port 143)

Some servers use STARTTLS on port 143:

```bash
email-analyzer mailbox add \
  --name "Email" \
  --provider imap \
  --email you@example.com \
  --host imap.example.com \
  --port 143
```

---

## Troubleshooting

### Error: "Authentication failed"

Common causes:
1. **Wrong password**: Double-check your password
2. **Need App Password**: Your provider may require an App Password
3. **2FA enabled**: Generate an App Password
4. **IMAP disabled**: Enable IMAP in your email settings

### Error: "Connection refused"

1. Verify the hostname is correct
2. Check the port number (993 for SSL, 143 for STARTTLS)
3. Ensure your firewall allows outbound connections

### Error: "Certificate verify failed"

The server's SSL certificate couldn't be verified:
1. Check if the hostname matches the certificate
2. For self-signed certificates on private servers, contact your admin

### Error: "Login disabled"

Some providers disable IMAP login:
1. Enable IMAP in your email provider's settings
2. Some providers require you to enable "Less secure apps" or generate an App Password

### Error: "Connection timed out"

1. Check your internet connection
2. Verify the server hostname and port
3. Your firewall may be blocking the connection

### Slow extraction

IMAP extraction can be slower than API-based methods:
- Use smaller batch sizes: `--batch-size 50`
- Extraction speed depends on your connection and server

---

## Security Considerations

### Password Storage

Passwords are stored securely in `~/.email-analyzer/credentials/`:
- File permissions: `0600` (owner read/write only)
- Passwords are not logged or displayed

### Network Security

All IMAP connections use SSL/TLS encryption:
- Port 993: Implicit SSL (recommended)
- Port 143: STARTTLS upgrade

### Revoking Access

To revoke access:

1. Remove the mailbox from Email Corpus Analyzer:
   ```bash
   email-analyzer mailbox remove Email --delete-data
   ```

2. For App Passwords, revoke them in your email provider's settings

3. Consider changing your password if you used your main password

---

## Advanced Configuration

### Custom Folders

By default, the analyzer reads from INBOX. Future versions will support:
- Multiple folder selection
- Folder filtering

### Connection Pooling

The analyzer uses async IMAP connections for better performance:
- Multiple concurrent connections
- Automatic reconnection on errors

### Batch Size

Adjust batch size for your connection:

```bash
# For slow connections
email-analyzer extract --mailbox Email --batch-size 25

# For fast connections
email-analyzer extract --mailbox Email --batch-size 200
```

---

## Finding IMAP Settings

If you don't know your IMAP settings:

1. **Check your email provider's help documentation**
2. **Search for "[provider name] IMAP settings"**
3. **Common pattern**: `imap.[domain].com` on port 993

For self-hosted servers:
1. Contact your email administrator
2. Check your email client's current settings
3. Look for documentation in your hosting control panel
