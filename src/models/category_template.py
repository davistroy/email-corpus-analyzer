"""
CategoryTemplate data model.

Per data-model.md lines 389-411.
"""

from pydantic import BaseModel, Field


class CategoryTemplate(BaseModel):
    """Predefined category pattern for matching."""

    name: str = Field(..., min_length=1)
    keywords: list[str] = Field(..., min_length=1)
    domains: list[str] = Field(default_factory=list)
    description: str


# Predefined templates constant (FR-024)
PREDEFINED_TEMPLATES = [
    CategoryTemplate(
        name="Financial & Banking",
        keywords=["invoice", "payment", "bank", "statement", "bill", "credit", "transaction"],
        domains=["paypal.com", "chase.com", "bankofamerica.com", "stripe.com", "venmo.com"],
        description="Financial transactions, banking, and billing"
    ),
    CategoryTemplate(
        name="Shopping & E-commerce",
        keywords=["order", "shipped", "delivery", "purchase", "receipt", "tracking"],
        domains=["amazon.com", "ebay.com", "etsy.com", "shopify.com", "walmart.com"],
        description="Online shopping confirmations and shipping updates"
    ),
    CategoryTemplate(
        name="Social Media",
        keywords=["notification", "mentioned", "tagged", "friend", "follow", "like", "comment"],
        domains=["facebook.com", "twitter.com", "instagram.com", "linkedin.com", "tiktok.com"],
        description="Social media notifications and updates"
    ),
    CategoryTemplate(
        name="Newsletters & Marketing",
        keywords=["newsletter", "subscribe", "unsubscribe", "promotional", "offer", "deal", "sale"],
        domains=["mailchimp.com", "constantcontact.com", "sendgrid.net"],
        description="Marketing emails and newsletters"
    ),
    CategoryTemplate(
        name="Travel & Transportation",
        keywords=["flight", "booking", "reservation", "hotel", "itinerary", "ticket", "confirmation"],
        domains=["expedia.com", "booking.com", "airbnb.com", "uber.com", "lyft.com"],
        description="Travel bookings and transportation"
    ),
    CategoryTemplate(
        name="Account & Security",
        keywords=["password", "security", "verify", "authentication", "reset", "confirm", "alert"],
        domains=["noreply", "no-reply", "security"],
        description="Account security and verification emails"
    ),
]
