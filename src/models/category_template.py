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
# Expanded from 6 to 18 templates for comprehensive email categorization
PREDEFINED_TEMPLATES = [
    # -------------------------------------------------------------------------
    # Original 6 templates (enhanced with more keywords and domains)
    # -------------------------------------------------------------------------
    CategoryTemplate(
        name="Financial & Banking",
        keywords=[
            "invoice", "payment", "bank", "statement", "bill", "credit", "transaction",
            "deposit", "withdrawal", "transfer", "balance", "account", "refund",
            "receipt", "wire", "ach", "direct deposit", "overdraft", "fee"
        ],
        domains=[
            "paypal.com", "chase.com", "bankofamerica.com", "stripe.com", "venmo.com",
            "wellsfargo.com", "citibank.com", "capitalone.com", "discover.com",
            "americanexpress.com", "usbank.com", "pnc.com", "tdbank.com", "ally.com",
            "schwab.com", "fidelity.com", "vanguard.com", "mint.com", "quickbooks.com"
        ],
        description="Financial transactions, banking, and billing"
    ),
    CategoryTemplate(
        name="Shopping & E-commerce",
        keywords=[
            "order", "shipped", "delivery", "purchase", "receipt", "tracking",
            "package", "arrived", "dispatched", "cart", "checkout", "return",
            "exchange", "refund", "wishlist", "out for delivery", "carrier"
        ],
        domains=[
            "amazon.com", "ebay.com", "etsy.com", "shopify.com", "walmart.com",
            "target.com", "bestbuy.com", "costco.com", "homedepot.com", "lowes.com",
            "macys.com", "nordstrom.com", "wayfair.com", "overstock.com", "newegg.com",
            "aliexpress.com", "wish.com", "zappos.com", "kohls.com", "jcpenney.com"
        ],
        description="Online shopping confirmations and shipping updates"
    ),
    CategoryTemplate(
        name="Social Media",
        keywords=[
            "notification", "mentioned", "tagged", "friend", "follow", "like", "comment",
            "post", "share", "message", "reply", "retweet", "story", "connection",
            "invite", "request", "profile", "update", "activity"
        ],
        domains=[
            "facebook.com", "twitter.com", "instagram.com", "linkedin.com", "tiktok.com",
            "pinterest.com", "snapchat.com", "reddit.com", "tumblr.com", "discord.com",
            "whatsapp.com", "telegram.org", "signal.org", "x.com", "threads.net",
            "mastodon.social", "youtube.com", "twitch.tv"
        ],
        description="Social media notifications and updates"
    ),
    CategoryTemplate(
        name="Newsletters & Marketing",
        keywords=[
            "newsletter", "subscribe", "unsubscribe", "promotional", "offer", "deal", "sale",
            "discount", "coupon", "promo", "exclusive", "limited time", "flash sale",
            "clearance", "weekly", "monthly", "digest", "roundup", "update"
        ],
        domains=[
            "mailchimp.com", "constantcontact.com", "sendgrid.net", "mailgun.com",
            "campaign-archive.com", "email.mg", "createsend.com", "aweber.com",
            "getresponse.com", "hubspot.com", "convertkit.com", "drip.com"
        ],
        description="Marketing emails and newsletters"
    ),
    CategoryTemplate(
        name="Travel & Transportation",
        keywords=[
            "flight", "booking", "reservation", "hotel", "itinerary", "ticket", "confirmation",
            "boarding pass", "check-in", "departure", "arrival", "trip", "vacation",
            "rental car", "cruise", "train", "bus", "ride", "destination"
        ],
        domains=[
            "expedia.com", "booking.com", "airbnb.com", "uber.com", "lyft.com",
            "kayak.com", "tripadvisor.com", "hotels.com", "vrbo.com", "priceline.com",
            "southwest.com", "delta.com", "united.com", "aa.com", "jetblue.com",
            "amtrak.com", "hertz.com", "enterprise.com", "marriott.com", "hilton.com"
        ],
        description="Travel bookings and transportation"
    ),
    CategoryTemplate(
        name="Account & Security",
        keywords=[
            "password", "security", "verify", "authentication", "reset", "confirm", "alert",
            "login", "signin", "two-factor", "2fa", "mfa", "suspicious", "unauthorized",
            "breach", "compromised", "protect", "update credentials", "recovery"
        ],
        domains=[
            "noreply", "no-reply", "security", "auth", "verify", "account",
            "notifications", "alerts", "support"
        ],
        description="Account security and verification emails"
    ),

    # -------------------------------------------------------------------------
    # New templates (12 additional categories)
    # -------------------------------------------------------------------------
    CategoryTemplate(
        name="Work & Office",
        keywords=[
            "meeting", "calendar", "deadline", "project", "agenda", "schedule",
            "conference", "standup", "review", "presentation", "report", "task",
            "assigned", "due date", "milestone", "sprint", "quarterly", "annual"
        ],
        domains=[
            "zoom.us", "teams.microsoft.com", "slack.com", "asana.com", "trello.com",
            "monday.com", "notion.so", "basecamp.com", "jira.atlassian.com",
            "confluence.atlassian.com", "dropbox.com", "box.com", "salesforce.com",
            "docusign.com", "adobe.com", "calendly.com", "webex.com"
        ],
        description="Work meetings, calendars, and office communications"
    ),
    CategoryTemplate(
        name="Healthcare & Medical",
        keywords=[
            "appointment", "prescription", "doctor", "medical", "health", "patient",
            "pharmacy", "lab results", "test results", "diagnosis", "treatment",
            "referral", "clinic", "hospital", "insurance claim", "copay", "provider"
        ],
        domains=[
            "myhealth.va.gov", "mychart.com", "healthgrades.com", "zocdoc.com",
            "cvs.com", "walgreens.com", "express-scripts.com", "goodrx.com",
            "onemedical.com", "teladoc.com", "mdlive.com", "labcorp.com",
            "questdiagnostics.com", "unitedhealth.com", "anthem.com"
        ],
        description="Healthcare appointments, prescriptions, and medical records"
    ),
    CategoryTemplate(
        name="Education & Learning",
        keywords=[
            "course", "assignment", "grade", "class", "student", "enrollment",
            "lecture", "homework", "exam", "quiz", "syllabus", "semester",
            "tuition", "scholarship", "certificate", "degree", "transcript"
        ],
        domains=[
            "coursera.org", "udemy.com", "edx.org", "khanacademy.org", "skillshare.com",
            "linkedin.com", "canvas.instructure.com", "blackboard.com", "moodle.org",
            "google.com", "microsoft.com", "duolingo.com", "masterclass.com",
            "pluralsight.com", "codecademy.com", "udacity.com"
        ],
        description="Educational courses, assignments, and academic communications"
    ),
    CategoryTemplate(
        name="Entertainment & Streaming",
        keywords=[
            "streaming", "movie", "show", "subscription", "watch", "episode",
            "series", "playlist", "album", "song", "concert", "event", "premiere",
            "new release", "recommendation", "continue watching", "queue"
        ],
        domains=[
            "netflix.com", "spotify.com", "hulu.com", "disneyplus.com", "hbomax.com",
            "primevideo.com", "apple.com", "peacocktv.com", "paramountplus.com",
            "youtube.com", "twitch.tv", "pandora.com", "tidal.com", "deezer.com",
            "soundcloud.com", "bandcamp.com", "ticketmaster.com", "stubhub.com"
        ],
        description="Streaming services, entertainment subscriptions, and media"
    ),
    CategoryTemplate(
        name="Government & Official",
        keywords=[
            "tax", "license", "permit", "official", "government", "irs", "dmv",
            "passport", "visa", "social security", "voter", "election", "jury",
            "court", "citation", "renewal", "application", "filing"
        ],
        domains=[
            "irs.gov", "ssa.gov", "usps.com", "dmv.gov", "state.gov",
            "uscis.gov", "va.gov", "usa.gov", "medicare.gov", "benefits.gov",
            "treasury.gov", "dot.gov", "fbi.gov", "dhs.gov", "ed.gov"
        ],
        description="Government services, tax notices, and official communications"
    ),
    CategoryTemplate(
        name="Utilities & Bills",
        keywords=[
            "bill", "electric", "water", "gas", "utility", "power", "energy",
            "usage", "meter", "kwh", "therms", "consumption", "autopay",
            "past due", "service", "outage", "internet", "cable", "phone"
        ],
        domains=[
            "xfinity.com", "att.com", "verizon.com", "tmobile.com", "spectrum.com",
            "pge.com", "sce.com", "coned.com", "dukeenergy.com", "dominion.com",
            "xcel.com", "entergy.com", "centerpoint.com", "nipsco.com"
        ],
        description="Utility bills, energy usage, and service notifications"
    ),
    CategoryTemplate(
        name="Real Estate & Housing",
        keywords=[
            "property", "rent", "lease", "mortgage", "home", "apartment", "listing",
            "landlord", "tenant", "move-in", "move-out", "inspection", "maintenance",
            "application", "showing", "open house", "closing", "escrow"
        ],
        domains=[
            "zillow.com", "realtor.com", "trulia.com", "redfin.com", "apartments.com",
            "rent.com", "hotpads.com", "cozy.co", "avail.co", "rentler.com",
            "buildium.com", "appfolio.com", "propertyware.com", "yardi.com"
        ],
        description="Real estate listings, rental notices, and property management"
    ),
    CategoryTemplate(
        name="Insurance",
        keywords=[
            "policy", "claim", "coverage", "premium", "deductible", "insurance",
            "renewal", "quote", "beneficiary", "auto insurance", "health insurance",
            "life insurance", "homeowners", "liability", "enrollment"
        ],
        domains=[
            "geico.com", "progressive.com", "statefarm.com", "allstate.com",
            "libertymutual.com", "nationwide.com", "usaa.com", "farmers.com",
            "travelers.com", "aetna.com", "cigna.com", "bluecross.com",
            "metlife.com", "prudential.com", "aflac.com"
        ],
        description="Insurance policies, claims, and coverage notifications"
    ),
    CategoryTemplate(
        name="Food & Dining",
        keywords=[
            "order", "delivery", "restaurant", "reservation", "menu", "pickup",
            "food", "meal", "groceries", "recipe", "dining", "takeout", "catering",
            "tip", "driver", "estimated arrival", "preparing"
        ],
        domains=[
            "doordash.com", "ubereats.com", "grubhub.com", "postmates.com",
            "instacart.com", "seamless.com", "caviar.com", "opentable.com",
            "resy.com", "yelp.com", "hellofresh.com", "blueapron.com",
            "freshly.com", "factor75.com", "chipotle.com", "dominos.com"
        ],
        description="Food delivery, restaurant reservations, and meal services"
    ),
    CategoryTemplate(
        name="Fitness & Wellness",
        keywords=[
            "workout", "exercise", "gym", "fitness", "training", "yoga", "meditation",
            "membership", "class", "session", "personal trainer", "nutrition",
            "calories", "steps", "goals", "challenge", "streak", "activity"
        ],
        domains=[
            "myfitnesspal.com", "fitbit.com", "strava.com", "peloton.com",
            "nike.com", "underarmour.com", "orangetheory.com", "classpass.com",
            "mindbody.com", "calm.com", "headspace.com", "noom.com",
            "beachbody.com", "equinox.com", "planetfitness.com"
        ],
        description="Fitness tracking, gym memberships, and wellness programs"
    ),
    CategoryTemplate(
        name="Charity & Donations",
        keywords=[
            "donation", "donate", "charity", "nonprofit", "give", "support",
            "contribution", "fundraiser", "campaign", "cause", "volunteer",
            "impact", "tax deductible", "receipt", "match", "monthly giving"
        ],
        domains=[
            "gofundme.com", "kickstarter.com", "indiegogo.com", "patreon.com",
            "donorbox.org", "classy.org", "networkforgood.com", "justgiving.com",
            "givebutter.com", "mightycause.com", "globalgiving.org",
            "redcross.org", "unicef.org", "worldwildlife.org"
        ],
        description="Charitable donations, fundraisers, and nonprofit communications"
    ),
    CategoryTemplate(
        name="Jobs & Career",
        keywords=[
            "job", "career", "application", "interview", "position", "hiring",
            "resume", "recruiter", "offer", "salary", "candidate", "apply",
            "opportunity", "employment", "linkedin", "referral", "screening"
        ],
        domains=[
            "indeed.com", "linkedin.com", "glassdoor.com", "monster.com",
            "ziprecruiter.com", "careerbuilder.com", "dice.com", "hired.com",
            "lever.co", "greenhouse.io", "workday.com", "icims.com",
            "smartrecruiters.com", "jobvite.com", "angel.co", "wellfound.com"
        ],
        description="Job applications, interviews, and career opportunities"
    ),
]
