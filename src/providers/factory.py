"""
Provider factory for creating email providers.

Creates appropriate provider instances based on configuration.
"""
from src.models.mailbox import Mailbox
from src.models.provider import (
    GmailConfig,
    IMAPConfig,
    M365Config,
    ProviderConfig,
    ProviderType,
)

from .base import EmailProvider


def create_provider(config: ProviderConfig) -> EmailProvider:
    """
    Create an email provider from configuration.

    Args:
        config: Provider-specific configuration.

    Returns:
        Configured EmailProvider instance.

    Raises:
        ValueError: If provider type is not supported.
    """
    if isinstance(config, M365Config):
        from .m365.provider import M365Provider
        return M365Provider(config)

    elif isinstance(config, GmailConfig):
        from .gmail.provider import GmailProvider
        return GmailProvider(config)

    elif isinstance(config, IMAPConfig):
        from .imap.provider import IMAPProvider
        return IMAPProvider(config)

    else:
        raise ValueError(f"Unsupported provider config type: {type(config)}")


def get_provider_for_mailbox(mailbox: Mailbox) -> EmailProvider:
    """
    Create an email provider for a mailbox.

    Args:
        mailbox: Mailbox configuration.

    Returns:
        Configured EmailProvider instance.

    Raises:
        ValueError: If mailbox provider is not supported.
    """
    # Reconstruct provider config from mailbox
    config_data = {
        "display_name": mailbox.name,
        "email_address": mailbox.email_address,
        **mailbox.provider_config,
    }

    if mailbox.provider == ProviderType.M365:
        config = M365Config(**config_data)
        from .m365.provider import M365Provider
        return M365Provider(config)

    elif mailbox.provider == ProviderType.GMAIL:
        config = GmailConfig(**config_data)
        from .gmail.provider import GmailProvider
        return GmailProvider(config)

    elif mailbox.provider == ProviderType.IMAP:
        config = IMAPConfig(**config_data)
        from .imap.provider import IMAPProvider
        return IMAPProvider(config)

    else:
        raise ValueError(f"Unsupported provider type: {mailbox.provider}")
