# M365 MCP Server Setup for Personal Accounts (Hotmail/Outlook.com)

## Issue

The M365 MCP server currently uses `/users/{email}/messages` endpoint which:
- ❌ **Does NOT work** with personal accounts (hotmail.com, outlook.com, live.com)
- ✅ **Only works** with organizational/work accounts with admin consent

For personal Microsoft accounts, you **must** use delegated authentication with `/me/messages` endpoint.

## Solution: Use Delegated Authentication

### Key Differences

| Endpoint | Auth Type | Works With | Requires |
|----------|-----------|------------|----------|
| `/users/{email}/messages` | Application | Work/School accounts only | Admin consent, client credentials |
| `/me/messages` | Delegated | Personal + Work accounts | User OAuth login |

### What the M365 MCP Server Needs to Do

The MCP server should:

1. **Use OAuth 2.0 Delegated Flow** (not client credentials)
2. **Call `/me/messages`** instead of `/users/{email}/messages`
3. **Store user's access token** from interactive login

## Setup Steps

### 1. Check M365 MCP Server Configuration

The M365 MCP server should be configured for **delegated permissions**:

```json
{
  "mcpServers": {
    "m365-email": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-m365"],
      "env": {
        "M365_CLIENT_ID": "your-client-id",
        "M365_CLIENT_SECRET": "your-client-secret",
        "M365_TENANT_ID": "common",  // Important: "common" for personal accounts
        "M365_AUTH_TYPE": "delegated"  // Not "application"
      }
    }
  }
}
```

**Critical settings for personal accounts:**
- `M365_TENANT_ID`: Must be `"common"` or `"consumers"` (not a specific tenant GUID)
- Authentication must use delegated flow with user login

### 2. Azure App Registration Settings

Your Azure AD app registration needs:

**API Permissions (Delegated):**
- ✅ `Mail.Read` (delegated)
- ✅ `Mail.ReadBasic` (delegated)
- ✅ `User.Read` (delegated)

**NOT** Application permissions - those don't work with personal accounts.

**Supported Account Types:**
- Must select: "Accounts in any organizational directory and personal Microsoft accounts"

### 3. Authentication Flow

For personal accounts, the MCP server needs to:

1. **Redirect user to Microsoft login** (OAuth 2.0 authorization code flow)
2. **User logs in** with troy.davis@hotmail.com
3. **User grants consent** to Mail.Read permission
4. **MCP server receives access token**
5. **Token is used for API calls** to `/me/messages`

### 4. Testing the Setup

#### Check if MCP server is authenticated:

```bash
# The M365 MCP server should have prompted for login when it started
# Check Claude Code MCP server logs for authentication status
```

#### Test email fetching:

Since the MCP server internally should use `/me/messages`, you shouldn't need to change your code. However, the **MCP server itself** needs to be updated to use the correct endpoint.

## Fixing the M365 MCP Server

The current MCP server implementation has a bug - it's using:
```
/users/{user_email}/messages
```

It should use:
```
/me/messages  (when using delegated auth)
```

### Option 1: Use Different MCP Server

Check if there's an updated version of the M365 MCP server:

```bash
npm info @modelcontextprotocol/server-m365
```

### Option 2: Modify MCP Server Source

If you're comfortable with TypeScript, you could:

1. Clone the MCP server repo
2. Update the endpoint from `/users/{email}` to `/me`
3. Run locally

### Option 3: Alternative - Direct Graph API

Instead of using the M365 MCP server, you could implement direct Microsoft Graph API calls:

```python
# See src/extractors/graph_api_client.py example in INTEGRATION.md
```

## Quick Test

Try this command to verify MCP authentication status:

```bash
# In Claude Code, check MCP server connection status
# The server should show as "connected" and "authenticated"
```

## Expected Behavior

**When working correctly:**

1. First run: Browser opens for Microsoft login
2. You login with troy.davis@hotmail.com
3. You grant Mail.Read permission
4. MCP server stores refresh token
5. Subsequent calls use stored token
6. Calls to `fetch_emails` work automatically

**Current error (404):**

The MCP server is trying:
```
GET /users/troy.davis@hotmail.com/messages
→ 404 Not Found (personal accounts not accessible via /users endpoint)
```

Should be trying:
```
GET /me/messages
→ 200 OK (with user's OAuth token)
```

## Workaround for Now

Until the MCP server is fixed, you can:

1. **Use a work/school account** (if you have one)
2. **Use direct Graph API calls** (bypass MCP)
3. **Use test data** (for development)

## Test Data Development Mode

To continue development without M365:

```bash
cd /home/davistroy/dev/email-processor/initial-learning

# Create test data
cat > outputs/test_emails.json <<'EOF'
{
  "extraction_metadata": {
    "extraction_date": "2025-10-05T12:00:00Z",
    "source_email": "test@example.com",
    "total_emails": 3,
    "extraction_duration_seconds": 1.0
  },
  "emails": [
    {
      "id": "msg_001",
      "sender_email": "deals@store.com",
      "sender_name": "Store Deals",
      "sender_domain": "store.com",
      "recipient_email": "troy.davis@hotmail.com",
      "recipient_name": "Troy Davis",
      "subject": "50% Off Sale Today Only!",
      "body_text": "Amazing deals! Click to shop now. Unsubscribe at bottom.",
      "received_date": "2025-10-01T10:00:00Z",
      "has_attachments": false
    },
    {
      "id": "msg_002",
      "sender_email": "noreply@github.com",
      "sender_name": "GitHub",
      "sender_domain": "github.com",
      "recipient_email": "troy.davis@hotmail.com",
      "recipient_name": "Troy Davis",
      "subject": "Security Alert: New SSH Key Added",
      "body_text": "A new SSH key was added to your account.",
      "received_date": "2025-10-02T14:30:00Z",
      "has_attachments": false
    },
    {
      "id": "msg_003",
      "sender_email": "friend@gmail.com",
      "sender_name": "Friend Name",
      "sender_domain": "gmail.com",
      "recipient_email": "troy.davis@hotmail.com",
      "recipient_name": "Troy Davis",
      "subject": "Hey, want to grab coffee?",
      "body_text": "Let me know when you're free this week!",
      "received_date": "2025-10-03T09:15:00Z",
      "has_attachments": false
    }
  ]
}
EOF

# Test analysis with test data
./venv/bin/python -m src.main analyze --input outputs/test_emails.json
```

## Next Steps

1. **Check MCP server version**: `npm list @modelcontextprotocol/server-m365`
2. **Verify authentication**: Look for OAuth login prompt
3. **Check MCP logs**: See what endpoints are being called
4. **File bug report**: If MCP server is using wrong endpoint for personal accounts
5. **Use workaround**: Test data or direct Graph API for now

## Resources

- [Microsoft Graph Personal Accounts](https://learn.microsoft.com/en-us/graph/auth/auth-concepts)
- [OAuth 2.0 Authorization Code Flow](https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-auth-code-flow)
- [Mail API Overview](https://learn.microsoft.com/en-us/graph/api/resources/mail-api-overview)
