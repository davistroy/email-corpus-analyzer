"""
Unit tests for expanded template library.

Tests that the template library has been expanded from 6 to 15+ templates
with comprehensive keyword and domain coverage.
"""

from src.generators.template_matcher import (
    _domain_matches,
    _get_keyword_pattern,
    match_templates,
)
from src.models.category_template import PREDEFINED_TEMPLATES, CategoryTemplate


# Helper to create minimal analysis results for testing
def create_test_analysis(
    cluster_subjects=None,
    cluster_body_previews=None,
    sender_domains=None,
    total_emails=1000,
):
    """Create minimal analysis results for template testing."""
    from src.models.analysis_results import (
        AnalysisResults,
        DomainCount,
        SenderAnalysis,
        SubjectPatterns,
        TemporalPatterns,
        VolumeStats,
    )
    from src.models.content_cluster import ContentCluster, RepresentativeSample
    from src.models.sender import Sender, SenderType

    clusters = []
    senders = []

    if cluster_subjects:
        body_previews = cluster_body_previews or ["Preview"] * len(cluster_subjects)
        samples = [
            RepresentativeSample(subject=subj, sender="test@test.com", body_preview=body)
            for subj, body in zip(cluster_subjects, body_previews, strict=True)
        ]
        clusters.append(ContentCluster(
            cluster_id=0,
            size=100,
            percentage=10.0,
            representative_samples=samples,
            common_domains=[],
            email_ids=[f"e{i}" for i in range(100)],
        ))

    if sender_domains:
        for i, domain in enumerate(sender_domains):
            senders.append(Sender(
                email=f"test@{domain}",
                name="Test",
                domain=domain,
                type=SenderType.SERVICE,
                frequency_count=50,
                sample_subjects=["Test"],
                email_ids=[f"sender{i}_e{j}" for j in range(50)],
            ))

    return AnalysisResults(
        sender_analysis=SenderAnalysis(
            top_senders=senders,
            top_domains=[DomainCount(domain=s.domain, count=50) for s in senders] if senders else [],
            unique_senders=len(senders),
            unique_domains=len({s.domain for s in senders}) if senders else 0,
        ),
        subject_patterns=SubjectPatterns(
            common_prefixes={},
            numbered_patterns={},
            top_keywords=[],
            bracket_tags=[],
            total_subjects_analyzed=total_emails,
        ),
        content_clusters=clusters,
        temporal_patterns=TemporalPatterns(
            frequency_distribution={},
            sender_frequencies={},
        ),
        volume_stats=VolumeStats(
            total_emails=total_emails,
            unique_senders=len(senders),
            date_range={"oldest": "2024-01-01", "newest": "2024-12-31", "span_days": "365"},
            with_attachments=0,
            attachment_percentage=0.0,
            avg_body_length_chars=500,
            emails_per_day=2.7,
        ),
    )


# -----------------------------------------------------------------------------
# Template Library Expansion Tests
# -----------------------------------------------------------------------------

class TestExpandedTemplateLibrary:
    """Tests for expanded template library (6 -> 15+ templates)."""

    def test_template_count_minimum_15(self):
        """Template library should have at least 15 templates."""
        assert len(PREDEFINED_TEMPLATES) >= 15, \
            f"Expected at least 15 templates, got {len(PREDEFINED_TEMPLATES)}"

    def test_all_templates_have_required_fields(self):
        """All templates should have name, keywords, domains, description."""
        for template in PREDEFINED_TEMPLATES:
            assert template.name, "Template must have a name"
            assert template.keywords, "Template must have keywords"
            assert template.description, "Template must have a description"

    def test_all_templates_have_minimum_keywords(self):
        """All templates should have at least 5 keywords."""
        for template in PREDEFINED_TEMPLATES:
            assert len(template.keywords) >= 5, \
                f"Template '{template.name}' has only {len(template.keywords)} keywords, need at least 5"


class TestExistingTemplatesEnhanced:
    """Test that existing 6 templates have enhanced keywords/domains."""

    def test_financial_template_enhanced(self):
        """Financial template should have enhanced keywords."""
        financial = next(t for t in PREDEFINED_TEMPLATES if "Financial" in t.name)

        expected_keywords = ["invoice", "payment", "bank", "statement", "credit"]
        for kw in expected_keywords:
            assert kw in financial.keywords, f"'{kw}' should be in Financial keywords"

        # Should have at least 5 domains
        assert len(financial.domains) >= 5, "Financial should have at least 5 domains"

    def test_shopping_template_enhanced(self):
        """Shopping template should have enhanced keywords."""
        shopping = next(t for t in PREDEFINED_TEMPLATES if "Shopping" in t.name)

        expected_keywords = ["order", "shipped", "delivery", "purchase", "tracking"]
        for kw in expected_keywords:
            assert kw in shopping.keywords, f"'{kw}' should be in Shopping keywords"

    def test_social_media_template_enhanced(self):
        """Social Media template should have enhanced keywords."""
        social = next(t for t in PREDEFINED_TEMPLATES if "Social" in t.name)

        expected_keywords = ["notification", "friend", "follow", "like", "comment"]
        for kw in expected_keywords:
            assert kw in social.keywords, f"'{kw}' should be in Social Media keywords"

    def test_newsletters_template_enhanced(self):
        """Newsletters template should have enhanced keywords."""
        newsletters = next(t for t in PREDEFINED_TEMPLATES if "Newsletter" in t.name)

        expected_keywords = ["newsletter", "subscribe", "unsubscribe"]
        for kw in expected_keywords:
            assert kw in newsletters.keywords, f"'{kw}' should be in Newsletters keywords"

    def test_travel_template_enhanced(self):
        """Travel template should have enhanced keywords."""
        travel = next(t for t in PREDEFINED_TEMPLATES if "Travel" in t.name)

        expected_keywords = ["flight", "booking", "hotel", "itinerary"]
        for kw in expected_keywords:
            assert kw in travel.keywords, f"'{kw}' should be in Travel keywords"

    def test_security_template_enhanced(self):
        """Security template should have enhanced keywords."""
        security = next(t for t in PREDEFINED_TEMPLATES if "Security" in t.name)

        expected_keywords = ["password", "security", "verify", "authentication"]
        for kw in expected_keywords:
            assert kw in security.keywords, f"'{kw}' should be in Security keywords"


class TestNewTemplates:
    """Test that new templates exist with proper configuration."""

    def test_work_template_exists(self):
        """Work/Office template should exist."""
        work_templates = [t for t in PREDEFINED_TEMPLATES if "Work" in t.name or "Office" in t.name]
        assert len(work_templates) >= 1, "Work/Office template should exist"

        work = work_templates[0]
        expected_keywords = ["meeting", "calendar", "deadline", "project", "agenda"]
        for kw in expected_keywords:
            assert kw in work.keywords, f"'{kw}' should be in Work keywords"

    def test_healthcare_template_exists(self):
        """Healthcare template should exist."""
        healthcare_templates = [t for t in PREDEFINED_TEMPLATES if "Health" in t.name]
        assert len(healthcare_templates) >= 1, "Healthcare template should exist"

        health = healthcare_templates[0]
        expected_keywords = ["appointment", "prescription", "doctor", "medical"]
        matching = sum(1 for kw in expected_keywords if kw in health.keywords)
        assert matching >= 3, f"Healthcare should have at least 3 of {expected_keywords}"

    def test_education_template_exists(self):
        """Education template should exist."""
        edu_templates = [t for t in PREDEFINED_TEMPLATES if "Education" in t.name or "School" in t.name]
        assert len(edu_templates) >= 1, "Education template should exist"

        edu = edu_templates[0]
        expected_keywords = ["course", "assignment", "grade", "class", "student"]
        matching = sum(1 for kw in expected_keywords if kw in edu.keywords)
        assert matching >= 3, f"Education should have at least 3 of {expected_keywords}"

    def test_entertainment_template_exists(self):
        """Entertainment template should exist."""
        ent_templates = [t for t in PREDEFINED_TEMPLATES if "Entertainment" in t.name]
        assert len(ent_templates) >= 1, "Entertainment template should exist"

        ent = ent_templates[0]
        expected_keywords = ["streaming", "movie", "show", "subscription"]
        matching = sum(1 for kw in expected_keywords if kw in ent.keywords)
        assert matching >= 2, f"Entertainment should have at least 2 of {expected_keywords}"

    def test_government_template_exists(self):
        """Government template should exist."""
        gov_templates = [t for t in PREDEFINED_TEMPLATES if "Government" in t.name]
        assert len(gov_templates) >= 1, "Government template should exist"

        gov = gov_templates[0]
        expected_keywords = ["tax", "license", "permit", "official"]
        matching = sum(1 for kw in expected_keywords if kw in gov.keywords)
        assert matching >= 2, f"Government should have at least 2 of {expected_keywords}"

    def test_utilities_template_exists(self):
        """Utilities template should exist."""
        util_templates = [t for t in PREDEFINED_TEMPLATES if "Utilit" in t.name]
        assert len(util_templates) >= 1, "Utilities template should exist"

        util = util_templates[0]
        expected_keywords = ["bill", "electric", "water", "gas"]
        matching = sum(1 for kw in expected_keywords if kw in util.keywords)
        assert matching >= 2, f"Utilities should have at least 2 of {expected_keywords}"

    def test_real_estate_template_exists(self):
        """Real Estate template should exist."""
        re_templates = [t for t in PREDEFINED_TEMPLATES if "Real Estate" in t.name or "Housing" in t.name]
        assert len(re_templates) >= 1, "Real Estate template should exist"

    def test_insurance_template_exists(self):
        """Insurance template should exist."""
        ins_templates = [t for t in PREDEFINED_TEMPLATES if "Insurance" in t.name]
        assert len(ins_templates) >= 1, "Insurance template should exist"

    def test_food_template_exists(self):
        """Food/Restaurant template should exist."""
        food_templates = [t for t in PREDEFINED_TEMPLATES if "Food" in t.name or "Restaurant" in t.name or "Dining" in t.name]
        assert len(food_templates) >= 1, "Food/Dining template should exist"

    def test_fitness_template_exists(self):
        """Fitness/Health template should exist."""
        # Could be combined with healthcare or separate
        fitness_templates = [t for t in PREDEFINED_TEMPLATES if "Fitness" in t.name or "Gym" in t.name or "Wellness" in t.name]
        assert len(fitness_templates) >= 1, "Fitness template should exist"

    def test_charity_template_exists(self):
        """Charity/Nonprofit template should exist."""
        charity_templates = [t for t in PREDEFINED_TEMPLATES if "Charit" in t.name or "Nonprofit" in t.name or "Donation" in t.name]
        assert len(charity_templates) >= 1, "Charity template should exist"

    def test_jobs_template_exists(self):
        """Jobs/Career template should exist."""
        jobs_templates = [t for t in PREDEFINED_TEMPLATES if "Job" in t.name or "Career" in t.name or "Employment" in t.name]
        assert len(jobs_templates) >= 1, "Jobs template should exist"


class TestTemplateMatching:
    """Test that templates match expected content."""

    def test_work_template_matches_meeting_emails(self):
        """Work template should match meeting-related emails."""
        analysis = create_test_analysis(
            cluster_subjects=["Meeting invitation: Q4 Planning", "Calendar reminder: Team standup"],
            cluster_body_previews=["You've been invited to a meeting", "Your meeting starts in 15 minutes"],
        )

        categories = match_templates(analysis, PREDEFINED_TEMPLATES)

        work_cats = [c for c in categories if "Work" in c.category_name or "Office" in c.category_name]
        assert len(work_cats) >= 1, "Work template should match meeting emails"

    def test_healthcare_template_matches_appointments(self):
        """Healthcare template should match appointment emails."""
        analysis = create_test_analysis(
            cluster_subjects=["Appointment reminder", "Your prescription is ready"],
            cluster_body_previews=["Your appointment with Dr. Smith is tomorrow", "Prescription pickup available"],
        )

        categories = match_templates(analysis, PREDEFINED_TEMPLATES)

        health_cats = [c for c in categories if "Health" in c.category_name]
        assert len(health_cats) >= 1, "Healthcare template should match appointment emails"

    def test_jobs_template_matches_application_emails(self):
        """Jobs template should match job application emails."""
        analysis = create_test_analysis(
            cluster_subjects=["Application received", "Interview invitation"],
            cluster_body_previews=["Thank you for applying", "We'd like to schedule an interview"],
        )

        categories = match_templates(analysis, PREDEFINED_TEMPLATES)

        job_cats = [c for c in categories if "Job" in c.category_name or "Career" in c.category_name]
        assert len(job_cats) >= 1, "Jobs template should match application emails"

    def test_entertainment_template_matches_streaming(self):
        """Entertainment template should match streaming service emails."""
        analysis = create_test_analysis(
            sender_domains=["netflix.com", "spotify.com", "hulu.com"],
        )

        categories = match_templates(analysis, PREDEFINED_TEMPLATES)

        ent_cats = [c for c in categories if "Entertainment" in c.category_name]
        assert len(ent_cats) >= 1, "Entertainment template should match streaming domains"


class TestTemplateUniqueness:
    """Test that templates are properly differentiated."""

    def test_no_duplicate_template_names(self):
        """No two templates should have the same name."""
        names = [t.name for t in PREDEFINED_TEMPLATES]
        assert len(names) == len(set(names)), "Template names should be unique"

    def test_templates_cover_diverse_categories(self):
        """Templates should cover diverse categories of email."""
        categories = set()
        for template in PREDEFINED_TEMPLATES:
            # Extract category type from name
            name_lower = template.name.lower()
            if "financ" in name_lower or "bank" in name_lower:
                categories.add("financial")
            elif "shop" in name_lower or "commerce" in name_lower:
                categories.add("shopping")
            elif "social" in name_lower:
                categories.add("social")
            elif "travel" in name_lower:
                categories.add("travel")
            elif "work" in name_lower or "office" in name_lower:
                categories.add("work")
            elif "health" in name_lower or "medical" in name_lower:
                categories.add("health")
            elif "edu" in name_lower or "school" in name_lower:
                categories.add("education")
            elif "entertain" in name_lower:
                categories.add("entertainment")
            elif "gov" in name_lower:
                categories.add("government")
            elif "utilit" in name_lower:
                categories.add("utilities")
            else:
                categories.add("other")

        assert len(categories) >= 8, f"Should cover at least 8 diverse categories, got {len(categories)}"


# -----------------------------------------------------------------------------
# Word-Boundary Keyword Matching Tests (false-positive prevention)
# -----------------------------------------------------------------------------

class TestKeywordWordBoundaryMatching:
    """Test that keyword matching uses word boundaries to prevent false positives."""

    def test_visa_does_not_match_provisioning(self):
        """'visa' keyword should NOT match 'provisioning' in subject/body."""
        analysis = create_test_analysis(
            cluster_subjects=["Server provisioning complete"],
            cluster_body_previews=["Your provisioning request has been processed"],
        )

        # Government template contains "visa" keyword
        gov_template = next(t for t in PREDEFINED_TEMPLATES if "Government" in t.name)
        categories = match_templates(analysis, [gov_template])

        assert len(categories) == 0, (
            "'visa' should not match 'provisioning' — word-boundary matching required"
        )

    def test_visa_does_not_match_advisory(self):
        """'visa' keyword should NOT match 'advisory' in subject/body."""
        analysis = create_test_analysis(
            cluster_subjects=["Security advisory notice"],
            cluster_body_previews=["Please review this advisory for your team"],
        )

        gov_template = next(t for t in PREDEFINED_TEMPLATES if "Government" in t.name)
        categories = match_templates(analysis, [gov_template])

        # "advisory" should not trigger the "visa" keyword, but might match other
        # government keywords. Let's test directly with a minimal template.
        minimal_template = CategoryTemplate(
            name="Visa Only Test",
            keywords=["visa"],
            domains=[],
            description="Test template with only visa keyword",
        )
        categories = match_templates(analysis, [minimal_template])
        assert len(categories) == 0, (
            "'visa' should not match 'advisory' — word-boundary matching required"
        )

    def test_visa_matches_actual_visa_word(self):
        """'visa' keyword SHOULD match when 'visa' appears as a whole word."""
        analysis = create_test_analysis(
            cluster_subjects=["Your visa application status"],
            cluster_body_previews=["Your visa has been approved"],
        )

        minimal_template = CategoryTemplate(
            name="Visa Test",
            keywords=["visa"],
            domains=[],
            description="Test template with visa keyword",
        )
        categories = match_templates(analysis, [minimal_template])
        assert len(categories) == 1, "'visa' should match 'visa' as a whole word"

    def test_bill_does_not_match_billboard(self):
        """'bill' keyword should NOT match 'billboard'."""
        analysis = create_test_analysis(
            cluster_subjects=["Billboard Hot 100 charts"],
            cluster_body_previews=["Check out the latest billboard rankings"],
        )

        minimal_template = CategoryTemplate(
            name="Bill Test",
            keywords=["bill"],
            domains=[],
            description="Test template with bill keyword",
        )
        categories = match_templates(analysis, [minimal_template])
        assert len(categories) == 0, (
            "'bill' should not match 'billboard' — word-boundary matching required"
        )

    def test_bill_matches_actual_bill_word(self):
        """'bill' keyword SHOULD match when 'bill' appears as a whole word."""
        analysis = create_test_analysis(
            cluster_subjects=["Your monthly bill is ready"],
            cluster_body_previews=["Your bill of $45.99 is due"],
        )

        minimal_template = CategoryTemplate(
            name="Bill Test",
            keywords=["bill"],
            domains=[],
            description="Test template with bill keyword",
        )
        categories = match_templates(analysis, [minimal_template])
        assert len(categories) == 1, "'bill' should match 'bill' as a whole word"

    def test_tax_does_not_match_taxonomy(self):
        """'tax' keyword should NOT match 'taxonomy'."""
        analysis = create_test_analysis(
            cluster_subjects=["Updated product taxonomy"],
            cluster_body_previews=["The taxonomy has been reorganized"],
        )

        minimal_template = CategoryTemplate(
            name="Tax Test",
            keywords=["tax"],
            domains=[],
            description="Test template with tax keyword",
        )
        categories = match_templates(analysis, [minimal_template])
        assert len(categories) == 0, (
            "'tax' should not match 'taxonomy' — word-boundary matching required"
        )

    def test_multiword_keyword_matches(self):
        """Multi-word keywords like 'direct deposit' should match correctly."""
        analysis = create_test_analysis(
            cluster_subjects=["Your direct deposit is pending"],
            cluster_body_previews=["Direct deposit of $3,500 will arrive Friday"],
        )

        minimal_template = CategoryTemplate(
            name="Direct Deposit Test",
            keywords=["direct deposit"],
            domains=[],
            description="Test multi-word keyword",
        )
        categories = match_templates(analysis, [minimal_template])
        assert len(categories) == 1, "Multi-word keyword 'direct deposit' should match"


# -----------------------------------------------------------------------------
# Domain Suffix Matching Tests (false-positive prevention)
# -----------------------------------------------------------------------------

class TestDomainSuffixMatching:
    """Test that domain matching uses suffix-based logic to prevent false positives."""

    def test_amazon_com_does_not_match_notamazon_com(self):
        """'amazon.com' should NOT match 'notamazon.com'."""
        analysis = create_test_analysis(
            sender_domains=["notamazon.com"],
        )

        minimal_template = CategoryTemplate(
            name="Amazon Test",
            keywords=["zzz_no_match_placeholder"],
            domains=["amazon.com"],
            description="Test domain matching",
        )
        categories = match_templates(analysis, [minimal_template])
        assert len(categories) == 0, (
            "'amazon.com' should not match 'notamazon.com' — suffix matching required"
        )

    def test_amazon_com_matches_exact_amazon_com(self):
        """'amazon.com' SHOULD match 'amazon.com' exactly."""
        analysis = create_test_analysis(
            sender_domains=["amazon.com"],
        )

        minimal_template = CategoryTemplate(
            name="Amazon Test",
            keywords=["zzz_no_match_placeholder"],
            domains=["amazon.com"],
            description="Test domain matching",
        )
        categories = match_templates(analysis, [minimal_template])
        assert len(categories) == 1, "'amazon.com' should match 'amazon.com' exactly"

    def test_amazon_com_matches_subdomain(self):
        """'amazon.com' SHOULD match 'mail.amazon.com' (subdomain)."""
        analysis = create_test_analysis(
            sender_domains=["mail.amazon.com"],
        )

        minimal_template = CategoryTemplate(
            name="Amazon Test",
            keywords=["zzz_no_match_placeholder"],
            domains=["amazon.com"],
            description="Test domain matching",
        )
        categories = match_templates(analysis, [minimal_template])
        assert len(categories) == 1, (
            "'amazon.com' should match 'mail.amazon.com' via subdomain suffix"
        )

    def test_mail_domain_does_not_match_email_example_com(self):
        """'mail' in domain list should NOT match 'email.example.com'."""
        # The old code would match because 'mail' is a substring of 'email'
        analysis = create_test_analysis(
            sender_domains=["email.example.com"],
        )

        minimal_template = CategoryTemplate(
            name="Mail Test",
            keywords=["zzz_no_match_placeholder"],
            domains=["mail"],
            description="Test domain matching",
        )
        categories = match_templates(analysis, [minimal_template])
        assert len(categories) == 0, (
            "'mail' domain should not match 'email.example.com' — "
            "suffix matching requires exact or .suffix match"
        )

    def test_paypal_com_does_not_match_fakepaypal_com(self):
        """'paypal.com' should NOT match 'fakepaypal.com'."""
        analysis = create_test_analysis(
            sender_domains=["fakepaypal.com"],
        )

        minimal_template = CategoryTemplate(
            name="PayPal Test",
            keywords=["zzz_no_match_placeholder"],
            domains=["paypal.com"],
            description="Test domain matching",
        )
        categories = match_templates(analysis, [minimal_template])
        assert len(categories) == 0, (
            "'paypal.com' should not match 'fakepaypal.com'"
        )

    def test_domain_matching_is_case_insensitive(self):
        """Domain matching should be case-insensitive."""
        analysis = create_test_analysis(
            sender_domains=["Amazon.COM"],
        )

        minimal_template = CategoryTemplate(
            name="Amazon Test",
            keywords=["zzz_no_match_placeholder"],
            domains=["amazon.com"],
            description="Test domain matching",
        )
        categories = match_templates(analysis, [minimal_template])
        assert len(categories) == 1, "Domain matching should be case-insensitive"

    def test_cluster_domain_false_positive_prevented(self):
        """Domain false positive prevention should apply to cluster domains too."""
        from src.models.analysis_results import (
            AnalysisResults,
            SenderAnalysis,
            SubjectPatterns,
            TemporalPatterns,
            VolumeStats,
        )
        from src.models.content_cluster import ContentCluster, RepresentativeSample

        # Create analysis with a cluster that has a false-positive domain
        cluster = ContentCluster(
            cluster_id=0,
            size=100,
            percentage=10.0,
            representative_samples=[
                RepresentativeSample(subject="Test", sender="test@test.com", body_preview="Test")
            ],
            common_domains=[("notamazon.com", 50)],
            email_ids=[f"e{i}" for i in range(100)],
        )

        analysis = AnalysisResults(
            sender_analysis=SenderAnalysis(
                top_senders=[], top_domains=[], unique_senders=0, unique_domains=0,
            ),
            subject_patterns=SubjectPatterns(
                common_prefixes={}, numbered_patterns={}, top_keywords=[],
                bracket_tags=[], total_subjects_analyzed=1000,
            ),
            content_clusters=[cluster],
            temporal_patterns=TemporalPatterns(
                frequency_distribution={}, sender_frequencies={},
            ),
            volume_stats=VolumeStats(
                total_emails=1000, unique_senders=1,
                date_range={"oldest": "2024-01-01", "newest": "2024-12-31", "span_days": "365"},
                with_attachments=0, attachment_percentage=0.0,
                avg_body_length_chars=500, emails_per_day=2.7,
            ),
        )

        minimal_template = CategoryTemplate(
            name="Amazon Test",
            keywords=["zzz_no_match_placeholder"],
            domains=["amazon.com"],
            description="Test domain matching",
        )
        categories = match_templates(analysis, [minimal_template])
        assert len(categories) == 0, (
            "'amazon.com' should not match 'notamazon.com' in cluster common_domains"
        )


# -----------------------------------------------------------------------------
# Pre-compiled Pattern Tests
# -----------------------------------------------------------------------------

class TestPrecompiledPatterns:
    """Test that the pre-compiled pattern caching works correctly."""

    def test_get_keyword_pattern_returns_compiled_regex(self):
        """_get_keyword_pattern should return a compiled regex Pattern."""
        import re
        pattern = _get_keyword_pattern("visa")
        assert isinstance(pattern, re.Pattern), "Should return a compiled regex pattern"

    def test_get_keyword_pattern_caches_results(self):
        """Same keyword should return the same compiled pattern object."""
        pattern1 = _get_keyword_pattern("invoice")
        pattern2 = _get_keyword_pattern("invoice")
        assert pattern1 is pattern2, "Same keyword should return cached pattern (same object)"

    def test_get_keyword_pattern_case_insensitive_caching(self):
        """Keywords differing only in case should use the same cached pattern."""
        pattern1 = _get_keyword_pattern("Payment")
        pattern2 = _get_keyword_pattern("payment")
        assert pattern1 is pattern2, "Case-different keywords should use same cached pattern"

    def test_keyword_pattern_matches_whole_word(self):
        """Compiled pattern should match whole words only."""
        pattern = _get_keyword_pattern("visa")
        assert pattern.search("apply for a visa today") is not None
        assert pattern.search("visa application pending") is not None
        assert pattern.search("provisioning complete") is None
        assert pattern.search("advisory notice") is None

    def test_keyword_pattern_with_special_chars(self):
        """Keywords with special regex characters should be properly escaped."""
        pattern = _get_keyword_pattern("two-factor")
        assert pattern.search("enable two-factor authentication") is not None

    def test_domain_matches_exact(self):
        """_domain_matches should match exact domain."""
        assert _domain_matches("amazon.com", "amazon.com") is True

    def test_domain_matches_subdomain(self):
        """_domain_matches should match subdomain."""
        assert _domain_matches("mail.amazon.com", "amazon.com") is True
        assert _domain_matches("shipping.amazon.com", "amazon.com") is True

    def test_domain_matches_rejects_prefix_collision(self):
        """_domain_matches should reject domains that merely contain the template domain."""
        assert _domain_matches("notamazon.com", "amazon.com") is False
        assert _domain_matches("fakepaypal.com", "paypal.com") is False

    def test_domain_matches_rejects_unrelated(self):
        """_domain_matches should reject completely unrelated domains."""
        assert _domain_matches("google.com", "amazon.com") is False


# -----------------------------------------------------------------------------
# All 18 Templates Still Match Their Intended Emails
# -----------------------------------------------------------------------------

class TestAll18TemplatesMatchIntendedEmails:
    """Verify each of the 18 predefined templates matches its intended content."""

    def test_financial_template_matches(self):
        analysis = create_test_analysis(
            cluster_subjects=["Your payment has been received"],
            sender_domains=["chase.com"],
        )
        cats = match_templates(analysis, [PREDEFINED_TEMPLATES[0]])
        assert len(cats) == 1, "Financial template should match payment emails from chase.com"

    def test_shopping_template_matches(self):
        analysis = create_test_analysis(
            cluster_subjects=["Your order has shipped"],
            sender_domains=["amazon.com"],
        )
        cats = match_templates(analysis, [PREDEFINED_TEMPLATES[1]])
        assert len(cats) == 1, "Shopping template should match order emails from amazon.com"

    def test_social_media_template_matches(self):
        analysis = create_test_analysis(
            cluster_subjects=["You have a new notification"],
            sender_domains=["facebook.com"],
        )
        cats = match_templates(analysis, [PREDEFINED_TEMPLATES[2]])
        assert len(cats) == 1, "Social Media template should match notification emails"

    def test_newsletters_template_matches(self):
        analysis = create_test_analysis(
            cluster_subjects=["Weekly newsletter digest"],
            sender_domains=["mailchimp.com"],
        )
        cats = match_templates(analysis, [PREDEFINED_TEMPLATES[3]])
        assert len(cats) == 1, "Newsletters template should match newsletter emails"

    def test_travel_template_matches(self):
        analysis = create_test_analysis(
            cluster_subjects=["Your flight booking confirmation"],
            sender_domains=["expedia.com"],
        )
        cats = match_templates(analysis, [PREDEFINED_TEMPLATES[4]])
        assert len(cats) == 1, "Travel template should match booking emails"

    def test_security_template_matches(self):
        analysis = create_test_analysis(
            cluster_subjects=["Password reset requested"],
            cluster_body_previews=["Your password has been changed"],
        )
        cats = match_templates(analysis, [PREDEFINED_TEMPLATES[5]])
        assert len(cats) == 1, "Security template should match password reset emails"

    def test_work_template_matches(self):
        analysis = create_test_analysis(
            cluster_subjects=["Meeting invitation: Q4 planning"],
            sender_domains=["zoom.us"],
        )
        cats = match_templates(analysis, [PREDEFINED_TEMPLATES[6]])
        assert len(cats) == 1, "Work template should match meeting emails"

    def test_healthcare_template_matches(self):
        analysis = create_test_analysis(
            cluster_subjects=["Your appointment is confirmed"],
            sender_domains=["mychart.com"],
        )
        cats = match_templates(analysis, [PREDEFINED_TEMPLATES[7]])
        assert len(cats) == 1, "Healthcare template should match appointment emails"

    def test_education_template_matches(self):
        analysis = create_test_analysis(
            cluster_subjects=["New assignment posted for your course"],
            sender_domains=["coursera.org"],
        )
        cats = match_templates(analysis, [PREDEFINED_TEMPLATES[8]])
        assert len(cats) == 1, "Education template should match course/assignment emails"

    def test_entertainment_template_matches(self):
        analysis = create_test_analysis(
            cluster_subjects=["New episode available for streaming"],
            sender_domains=["netflix.com"],
        )
        cats = match_templates(analysis, [PREDEFINED_TEMPLATES[9]])
        assert len(cats) == 1, "Entertainment template should match streaming emails"

    def test_government_template_matches(self):
        analysis = create_test_analysis(
            cluster_subjects=["Your tax return has been accepted"],
            sender_domains=["irs.gov"],
        )
        cats = match_templates(analysis, [PREDEFINED_TEMPLATES[10]])
        assert len(cats) == 1, "Government template should match tax emails"

    def test_utilities_template_matches(self):
        analysis = create_test_analysis(
            cluster_subjects=["Your electric bill is ready"],
            sender_domains=["xfinity.com"],
        )
        cats = match_templates(analysis, [PREDEFINED_TEMPLATES[11]])
        assert len(cats) == 1, "Utilities template should match utility bill emails"

    def test_real_estate_template_matches(self):
        analysis = create_test_analysis(
            cluster_subjects=["New property listing matches your search"],
            sender_domains=["zillow.com"],
        )
        cats = match_templates(analysis, [PREDEFINED_TEMPLATES[12]])
        assert len(cats) == 1, "Real Estate template should match property listing emails"

    def test_insurance_template_matches(self):
        analysis = create_test_analysis(
            cluster_subjects=["Your policy renewal is due"],
            sender_domains=["geico.com"],
        )
        cats = match_templates(analysis, [PREDEFINED_TEMPLATES[13]])
        assert len(cats) == 1, "Insurance template should match policy renewal emails"

    def test_food_template_matches(self):
        analysis = create_test_analysis(
            cluster_subjects=["Your food delivery is on the way"],
            sender_domains=["doordash.com"],
        )
        cats = match_templates(analysis, [PREDEFINED_TEMPLATES[14]])
        assert len(cats) == 1, "Food template should match delivery emails"

    def test_fitness_template_matches(self):
        analysis = create_test_analysis(
            cluster_subjects=["Your workout summary for today"],
            sender_domains=["peloton.com"],
        )
        cats = match_templates(analysis, [PREDEFINED_TEMPLATES[15]])
        assert len(cats) == 1, "Fitness template should match workout emails"

    def test_charity_template_matches(self):
        analysis = create_test_analysis(
            cluster_subjects=["Thank you for your donation"],
            sender_domains=["gofundme.com"],
        )
        cats = match_templates(analysis, [PREDEFINED_TEMPLATES[16]])
        assert len(cats) == 1, "Charity template should match donation emails"

    def test_jobs_template_matches(self):
        analysis = create_test_analysis(
            cluster_subjects=["Your job application was received"],
            sender_domains=["indeed.com"],
        )
        cats = match_templates(analysis, [PREDEFINED_TEMPLATES[17]])
        assert len(cats) == 1, "Jobs template should match application emails"
