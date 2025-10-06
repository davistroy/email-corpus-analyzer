#!/usr/bin/env python3
"""
Terminal-based M365 Email Fetcher using Device Code Flow.

This script fetches emails from a Microsoft 365 account using the Microsoft Graph API
with device code authentication - no browser required on the same machine.

Usage:
    python fetch_emails_cli.py [--count 5] [--output emails.json]

Authentication:
    - First run: displays a code and URL
    - Go to https://microsoft.com/devicelogin on ANY device
    - Enter the code shown
    - Log in with your Microsoft account
    - Subsequent runs: uses cached token (no re-authentication needed)
"""
import argparse
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

import msal
import requests


# Public client application ID (Microsoft Graph Explorer - public client)
# This is a well-known public client ID from Microsoft for testing
CLIENT_ID = "14d82eec-204b-4c2f-b7e8-296a70dab67e"  # Microsoft Graph Explorer

# For personal accounts, use "common" tenant
TENANT_ID = "common"

# Scopes needed to read emails
SCOPES = ["Mail.Read", "User.Read"]

# Token cache file
TOKEN_CACHE_FILE = Path.home() / ".m365_email_token_cache.json"


class TokenCache:
    """Simple file-based token cache."""

    def __init__(self, cache_file: Path):
        self.cache_file = cache_file
        self.cache = msal.SerializableTokenCache()

        if cache_file.exists():
            self.cache.deserialize(cache_file.read_text())

    def save(self):
        """Save cache to file."""
        if self.cache.has_state_changed:
            self.cache_file.write_text(self.cache.serialize())

    def get_cache(self) -> msal.SerializableTokenCache:
        """Get the MSAL cache object."""
        return self.cache


def authenticate(force_new: bool = False) -> str:
    """
    Authenticate using device code flow and return access token.

    Args:
        force_new: Force new authentication even if cached token exists

    Returns:
        Access token string
    """
    # Initialize token cache
    token_cache = TokenCache(TOKEN_CACHE_FILE)

    # Create public client application
    app = msal.PublicClientApplication(
        CLIENT_ID,
        authority=f"https://login.microsoftonline.com/{TENANT_ID}",
        token_cache=token_cache.get_cache()
    )

    # Try to get token silently from cache first
    if not force_new:
        accounts = app.get_accounts()
        if accounts:
            print(f"Using cached credentials for {accounts[0]['username']}", file=sys.stderr)
            result = app.acquire_token_silent(SCOPES, account=accounts[0])
            if result and "access_token" in result:
                return result["access_token"]

    # Need to authenticate with device code
    print("\n" + "="*60, file=sys.stderr)
    print("DEVICE CODE AUTHENTICATION REQUIRED", file=sys.stderr)
    print("="*60, file=sys.stderr)

    flow = app.initiate_device_flow(scopes=SCOPES)

    if "user_code" not in flow:
        raise ValueError(f"Failed to create device flow: {flow.get('error_description')}")

    # Display instructions to user
    print(flow["message"], file=sys.stderr)
    print("="*60 + "\n", file=sys.stderr)

    # Wait for user to authenticate
    result = app.acquire_token_by_device_flow(flow)

    if "access_token" in result:
        # Save the token cache
        token_cache.save()
        print(f"\n✓ Authentication successful! Token cached for future use.", file=sys.stderr)
        return result["access_token"]
    else:
        raise Exception(f"Authentication failed: {result.get('error_description', 'Unknown error')}")


def fetch_emails(access_token: str, count: int = 5) -> List[Dict[str, Any]]:
    """
    Fetch emails from Microsoft Graph API.

    Args:
        access_token: OAuth access token
        count: Number of emails to fetch

    Returns:
        List of email dictionaries
    """
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    # Use /me/messages endpoint (works with personal and work accounts)
    url = "https://graph.microsoft.com/v1.0/me/messages"

    params = {
        "$top": min(count, 999),
        "$select": "id,subject,from,toRecipients,receivedDateTime,bodyPreview,body,hasAttachments",
        "$orderby": "receivedDateTime DESC"
    }

    print(f"Fetching {count} most recent emails...", file=sys.stderr)

    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()

    data = response.json()
    messages = data.get("value", [])

    print(f"✓ Fetched {len(messages)} emails", file=sys.stderr)

    return messages


def sanitize_email(email: str, default: str = "unknown@unknown.com") -> str:
    """
    Sanitize email address to ensure it's valid.

    Args:
        email: Email address to sanitize
        default: Default email if invalid

    Returns:
        Valid email address
    """
    if not email or not isinstance(email, str):
        return default

    # Remove whitespace and common wrapper characters
    email = email.strip().strip("'\"[]<>")

    # Check if valid format
    if '@' not in email:
        return default

    # Split into local and domain parts
    try:
        local, domain = email.rsplit('@', 1)
    except ValueError:
        return default

    # Remove invalid characters from domain
    # Remove underscores from domain (they're invalid in domain names and can create invalid patterns)
    domain = domain.replace('_', '')

    # Remove other invalid characters from domain
    domain = ''.join(c for c in domain if c.isalnum() or c in '.-')

    # Remove invalid characters from local part
    # Keep alphanumeric, dots, hyphens, underscores, plus signs
    local = ''.join(c for c in local if c.isalnum() or c in '._-+')

    # Check if we still have valid parts
    if not local or not domain or '.' not in domain:
        return default

    # Reconstruct email
    sanitized = f"{local}@{domain}"

    # Final validation - must have @ and at least one dot in domain
    if '@' not in sanitized or '.' not in sanitized.split('@')[1]:
        return default

    return sanitized


def parse_email(msg: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse Graph API message into simplified format.

    Args:
        msg: Raw message from Graph API

    Returns:
        Simplified email dictionary
    """
    # Extract sender info
    from_field = msg.get("from", {}).get("emailAddress", {})
    sender_email = sanitize_email(from_field.get("address", ""), "unknown@unknown.com")
    sender_name = from_field.get("name", sender_email)
    sender_domain = sender_email.split("@")[-1] if "@" in sender_email else "unknown.com"

    # Extract recipient info
    to_recipients = msg.get("toRecipients", [])
    recipient_email = "unknown@unknown.com"  # Default for required field
    recipient_name = ""
    if to_recipients:
        first_recipient = to_recipients[0].get("emailAddress", {})
        recipient_email = sanitize_email(
            first_recipient.get("address", ""),
            "unknown@unknown.com"
        )
        recipient_name = first_recipient.get("name", "")

    # Extract body
    body_data = msg.get("body", {})
    body_text = body_data.get("content", msg.get("bodyPreview", ""))

    # Parse date
    received_str = msg.get("receivedDateTime", "")

    return {
        "id": msg.get("id", ""),
        "sender_email": sender_email,
        "sender_name": sender_name,
        "sender_domain": sender_domain,
        "recipient_email": recipient_email,
        "recipient_name": recipient_name,
        "subject": msg.get("subject", "(No subject)"),
        "body_text": body_text,
        "body_preview": msg.get("bodyPreview", ""),
        "received_date": received_str,
        "has_attachments": msg.get("hasAttachments", False)
    }


def display_emails(emails: List[Dict[str, Any]]):
    """Display emails in a readable format."""
    print("\n" + "="*80)
    print(f"EMAILS ({len(emails)} messages)")
    print("="*80 + "\n")

    for i, email in enumerate(emails, 1):
        print(f"Email {i}:")
        print(f"  From: {email['sender_name']} <{email['sender_email']}>")
        print(f"  To: {email['recipient_name']} <{email['recipient_email']}>")
        print(f"  Subject: {email['subject']}")
        print(f"  Date: {email['received_date']}")
        print(f"  Preview: {email['body_preview'][:100]}...")
        print()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Fetch emails from Microsoft 365 using device code authentication"
    )
    parser.add_argument(
        "--count",
        type=int,
        default=5,
        help="Number of emails to fetch (default: 5)"
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output JSON file path (default: print to stdout)"
    )
    parser.add_argument(
        "--force-auth",
        action="store_true",
        help="Force new authentication (ignore cached token)"
    )
    parser.add_argument(
        "--display",
        action="store_true",
        help="Display emails in readable format (in addition to JSON output)"
    )
    parser.add_argument(
        "--user-email",
        type=str,
        help="User's M365 email address (optional, will be detected from token)"
    )

    args = parser.parse_args()

    try:
        # Authenticate
        access_token = authenticate(force_new=args.force_auth)

        # Get user email (from argument or token)
        if args.user_email:
            user_email = args.user_email
        else:
            # Try to extract from token or use a placeholder
            user_email = "user@microsoft.com"  # Will be overridden if we can detect it

        # Fetch emails
        raw_messages = fetch_emails(access_token, count=args.count)

        # Parse emails
        emails = [parse_email(msg) for msg in raw_messages]

        # Try to detect user email from first email's recipient
        if emails and not args.user_email:
            first_recipient = emails[0].get('recipient_email', '')
            if first_recipient and '@' in first_recipient:
                user_email = first_recipient

        # Create output structure matching Corpus model
        output = {
            "extraction_metadata": {
                "extraction_date": datetime.now().isoformat(),
                "total_emails": len(emails),
                "source": "M365/Hotmail (device_code_flow)",
                "user_email": user_email
            },
            "emails": emails
        }

        # Display if requested
        if args.display:
            display_emails(emails)

        # Output JSON
        if args.output:
            args.output.write_text(json.dumps(output, indent=2))
            print(f"\n✓ Saved {len(emails)} emails to {args.output}", file=sys.stderr)
        else:
            print(json.dumps(output, indent=2))

    except Exception as e:
        print(f"\n✗ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
