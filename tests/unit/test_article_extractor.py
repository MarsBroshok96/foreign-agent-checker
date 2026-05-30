from datetime import UTC

import pytest

from fa_checker.article.extractor import ArticleExtractionError, extract_article_from_html


def test_extract_article_from_html_gets_title_from_open_graph() -> None:
    html = """
    <html>
      <head>
        <meta property="og:title" content="OpenGraph title">
        <title>Title tag</title>
      </head>
      <body><article><p>Article body text.</p></article></body>
    </html>
    """

    article = extract_article_from_html("https://www.rambler.ru/news/example", html)

    assert article.title == "OpenGraph title"


def test_extract_article_from_html_gets_title_from_h1_fallback() -> None:
    html = """
    <html>
      <body>
        <h1>Heading title</h1>
        <article><p>Article body text.</p></article>
      </body>
    </html>
    """

    article = extract_article_from_html("https://www.rambler.ru/news/example", html)

    assert article.title == "Heading title"


def test_extract_article_from_html_gets_author_from_meta() -> None:
    html = """
    <html>
      <head><meta name="author" content="Reporter"></head>
      <body><article><p>Article body text.</p></article></body>
    </html>
    """

    article = extract_article_from_html("https://www.rambler.ru/news/example", html)

    assert article.author == "Reporter"


def test_extract_article_from_html_gets_author_from_json_ld_graph_article() -> None:
    html = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@graph": [
            {
              "@type": "ImageObject",
              "author": {"@type": "Organization", "name": "Photo Agency"}
            },
            {
              "@type": "Article",
              "author": {
                "@type": "Person",
                "name": "Марина Стрельникова"
              }
            }
          ]
        }
        </script>
      </head>
      <body><article><p>Article body text.</p></article></body>
    </html>
    """

    article = extract_article_from_html("https://www.rambler.ru/news/example", html)

    assert article.author == "Марина Стрельникова"


def test_extract_article_from_html_gets_published_at_from_meta() -> None:
    html = """
    <html>
      <head><meta property="article:published_time" content="2026-05-28T12:30:00Z"></head>
      <body><article><p>Article body text.</p></article></body>
    </html>
    """

    article = extract_article_from_html("https://www.rambler.ru/news/example", html)

    assert article.published_at is not None
    assert article.published_at.year == 2026
    assert article.published_at.tzinfo == UTC


def test_extract_article_from_html_extracts_main_text_from_article() -> None:
    html = """
    <html>
      <body>
        <nav>Navigation</nav>
        <article>
          <p>First paragraph.</p>
          <p>Second paragraph.</p>
        </article>
      </body>
    </html>
    """

    article = extract_article_from_html("https://www.rambler.ru/news/example", html)

    assert "First paragraph" in article.text
    assert "Second paragraph" in article.text


def test_extract_article_from_html_extracts_and_resolves_links() -> None:
    html = """
    <html>
      <body>
        <article>
          <p>Article body text.</p>
          <a href="/internal">Internal</a>
          <a href="https://example.org/page">External</a>
          <a href="mailto:test@example.org">Email</a>
          <a href="/internal">Duplicate</a>
        </article>
      </body>
    </html>
    """

    article = extract_article_from_html("https://www.rambler.ru/news/example", html)

    assert article.links == [
        "https://www.rambler.ru/internal",
        "https://example.org/page",
    ]


def test_extract_article_from_html_ignores_links_outside_article() -> None:
    html = """
    <html>
      <body>
        <nav><a href="https://example.org/nav">Navigation</a></nav>
        <article>
          <p>Article body text.</p>
          <a href="https://example.org/body">Body</a>
        </article>
        <footer><a href="https://example.org/footer">Footer</a></footer>
      </body>
    </html>
    """

    article = extract_article_from_html("https://www.rambler.ru/news/example", html)

    assert article.links == ["https://example.org/body"]


def test_extract_article_from_html_returns_no_links_without_article_tag() -> None:
    html = """
    <html>
      <body>
        <p>Article body text without article tag.</p>
        <a href="https://example.org/page">External</a>
      </body>
    </html>
    """

    article = extract_article_from_html("https://www.rambler.ru/news/example", html)

    assert article.links == []


def test_extract_article_from_html_raises_when_no_text_extracted() -> None:
    html = "<html><head><title>Only title</title></head><body></body></html>"

    with pytest.raises(ArticleExtractionError, match="Could not extract article text"):
        extract_article_from_html("https://www.rambler.ru/news/example", html)


def test_extract_article_from_html_normalizes_whitespace_in_text() -> None:
    html = """
    <html>
      <body>
        <article><p>First&nbsp;&nbsp; paragraph.</p><p>Second

        paragraph.</p></article>
      </body>
    </html>
    """

    article = extract_article_from_html("https://www.rambler.ru/news/example", html)

    assert "First paragraph." in article.text
    assert "\n\n" not in article.text
