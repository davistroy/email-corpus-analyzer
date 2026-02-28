"""
Unit tests for HTML parser.

Tests the extract_plain_text function with various HTML scenarios
including malformed HTML, scripts, styles, and edge cases.
"""

from unittest.mock import MagicMock, patch

import pytest

from src.extractors.html_parser import extract_plain_text


class TestHTMLParser:
    """Test cases for HTML parser."""

    def test_simple_html(self):
        """Test basic HTML to text conversion."""
        html = "<p>Hello world</p>"
        result = extract_plain_text(html)
        assert result == "Hello world"

    def test_html_with_tags(self):
        """Test HTML with multiple tags."""
        html = "<div><h1>Title</h1><p>Paragraph</p></div>"
        result = extract_plain_text(html)
        assert "Title" in result
        assert "Paragraph" in result

    def test_html_with_script_tags(self):
        """Test that script tags are removed."""
        html = '<div>Content<script>alert("bad")</script></div>'
        result = extract_plain_text(html)
        assert "Content" in result
        assert "alert" not in result
        assert "bad" not in result

    def test_html_with_style_tags(self):
        """Test that style tags are removed."""
        html = "<div>Content<style>body { color: red; }</style></div>"
        result = extract_plain_text(html)
        assert "Content" in result
        assert "color" not in result
        assert "red" not in result

    def test_malformed_html(self):
        """Test handling of malformed HTML."""
        html = "<p>Unclosed paragraph<div>Content"
        result = extract_plain_text(html)
        # Should still extract text despite malformed structure
        assert "Unclosed paragraph" in result
        assert "Content" in result

    def test_empty_html(self):
        """Test handling of empty HTML."""
        with pytest.raises(ValueError, match="cannot be None or empty"):
            extract_plain_text("")

    def test_none_input(self):
        """Test handling of None input."""
        with pytest.raises(ValueError, match="cannot be None or empty"):
            extract_plain_text(None)

    def test_html_entities(self):
        """Test HTML entity decoding."""
        html = "<p>Hello &amp; goodbye</p>"
        result = extract_plain_text(html)
        assert "&" in result

    def test_nested_tags(self):
        """Test deeply nested HTML tags."""
        html = "<div><div><div><p>Deep content</p></div></div></div>"
        result = extract_plain_text(html)
        assert "Deep content" in result

    def test_whitespace_handling(self):
        """Test that whitespace is properly stripped."""
        html = "<p>  Content with   spaces  </p>"
        result = extract_plain_text(html)
        assert result == "Content with spaces"

    def test_multiple_paragraphs(self):
        """Test multiple paragraphs are separated."""
        html = "<p>First paragraph</p><p>Second paragraph</p>"
        result = extract_plain_text(html)
        assert "First paragraph" in result
        assert "Second paragraph" in result

    def test_email_body_simulation(self):
        """Test realistic email HTML body."""
        html = """
        <html>
            <body>
                <div class="email-content">
                    <h2>Meeting Reminder</h2>
                    <p>Hi Team,</p>
                    <p>This is a reminder about our meeting tomorrow.</p>
                    <script>trackOpen();</script>
                </div>
            </body>
        </html>
        """
        result = extract_plain_text(html)
        assert "Meeting Reminder" in result
        assert "Hi Team" in result
        assert "trackOpen" not in result


class TestHTMLParserFallback:
    """Test cases for HTML parser fallback behavior when parsers fail."""

    def test_lxml_failure_falls_back_to_html_parser(self):
        """Test that lxml failure triggers html.parser fallback."""
        html = "<p>Test content</p>"

        # Mock BeautifulSoup to fail on first call (lxml), succeed on second (html.parser)
        with patch("src.extractors.html_parser.BeautifulSoup") as mock_bs:
            # Create a mock soup object for successful html.parser parsing
            mock_soup = MagicMock()
            mock_soup.return_value = []  # For soup(['script', 'style'])
            mock_soup.get_text.return_value = "Test content"

            # First call (lxml) raises, second call (html.parser) succeeds
            mock_bs.side_effect = [Exception("lxml not available"), mock_soup]

            extract_plain_text(html)

            # Verify both parsers were tried
            assert mock_bs.call_count == 2
            assert mock_bs.call_args_list[0][0][1] == "lxml"
            assert mock_bs.call_args_list[1][0][1] == "html.parser"

    def test_both_parsers_fail_returns_stripped_content(self):
        """Test that when both parsers fail, raw text with stripped tags is returned."""
        html = "<div>Important content</div>"

        # Mock BeautifulSoup to always fail
        with patch("src.extractors.html_parser.BeautifulSoup") as mock_bs:
            mock_bs.side_effect = Exception("Parser failed")

            result = extract_plain_text(html)

            # Should return content with HTML tags manually stripped
            # The fallback adds spaces around tags: "< div>Important content< /div>"
            assert "Important content" in result

    def test_fallback_with_complex_html_both_fail(self):
        """Test fallback behavior with more complex HTML when both parsers fail."""
        html = "<html><body><p>First</p><p>Second</p></body></html>"

        with patch("src.extractors.html_parser.BeautifulSoup") as mock_bs:
            mock_bs.side_effect = Exception("All parsers unavailable")

            result = extract_plain_text(html)

            # Content should still be extractable in some form
            assert "First" in result
            assert "Second" in result

    def test_fallback_strips_angle_brackets_properly(self):
        """Test that fallback strips HTML tags by adding spaces around brackets."""
        html = "<span>Hello</span><strong>World</strong>"

        with patch("src.extractors.html_parser.BeautifulSoup") as mock_bs:
            mock_bs.side_effect = Exception("Parser failure")

            result = extract_plain_text(html)

            # The fallback replaces < with " <" and > with "> "
            # This effectively separates tag content from text
            assert "Hello" in result
            assert "World" in result
