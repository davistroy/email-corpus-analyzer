"""
Provider type enumeration and configuration models.

Supports M365, Gmail, and IMAP providers.
"""
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, SecretStr


class ProviderType(Enum):
    """Supported email provider types."""
    M365 = "m365"
    GMAIL = "gmail"
    IMAP = "imap"


class BaseProviderConfig(BaseModel):
    """Base configuration for all providers."""
    provider_type: ProviderType
    display_name: str = Field(..., min_length=1, description="User-friendly name")
    email_address: str = Field(..., description="Email address for this mailbox")

    model_config = {"extra": "forbid"}


class M365Config(BaseProviderConfig):
    """M365-specific configuration."""
    provider_type: ProviderType = ProviderType.M365
    tenant_id: str | None = Field(
        default=None,
        description="Azure AD tenant ID. None for consumer accounts (uses 'consumers')"
    )
    client_id: str | None = Field(
        default=None,
        description="Azure AD application client ID for custom app registration"
    )
    # Token storage - refreshed automatically
    access_token: SecretStr | None = None
    refresh_token: SecretStr | None = None


class GmailConfig(BaseProviderConfig):
    """Gmail-specific configuration."""
    provider_type: ProviderType = ProviderType.GMAIL
    credentials_file: str = Field(
        ...,
        description="Path to OAuth credentials.json from Google Cloud Console"
    )
    token_file: str | None = Field(
        default=None,
        description="Path to store OAuth token (default: ~/.email-analyzer/tokens/{mailbox_id}.json)"
    )


class IMAPConfig(BaseProviderConfig):
    """IMAP-specific configuration."""
    provider_type: ProviderType = ProviderType.IMAP
    host: str = Field(..., description="IMAP server hostname")
    port: int = Field(default=993, description="IMAP server port")
    use_ssl: bool = Field(default=True, description="Use SSL/TLS connection")
    username: str | None = Field(
        default=None,
        description="Username if different from email_address"
    )
    password: SecretStr | None = Field(
        default=None,
        description="Password for authentication"
    )
    oauth2_token: SecretStr | None = Field(
        default=None,
        description="OAuth2 token for providers that support it"
    )


# Type alias for any provider config
ProviderConfig = M365Config | GmailConfig | IMAPConfig


def create_provider_config(provider_type: ProviderType, **kwargs: Any) -> ProviderConfig:
    """Factory function to create appropriate provider config."""
    config_classes = {
        ProviderType.M365: M365Config,
        ProviderType.GMAIL: GmailConfig,
        ProviderType.IMAP: IMAPConfig,
    }
    config_class = config_classes.get(provider_type)
    if not config_class:
        raise ValueError(f"Unknown provider type: {provider_type}")
    return config_class(provider_type=provider_type, **kwargs)
