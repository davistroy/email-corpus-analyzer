"""
Unit tests for HTML parser.

Tests the extract_plain_text function with various HTML scenarios
including malformed HTML, scripts, styles, and edge cases.
"""
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
