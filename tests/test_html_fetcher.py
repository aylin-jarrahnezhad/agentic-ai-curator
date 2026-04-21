from bs4 import BeautifulSoup

from services.fetch.html_fetcher import HTMLFetcher


def test_extract_published_uses_itemprop_datetime() -> None:
    soup = BeautifulSoup(
        """
        <html>
          <body>
            <article>
              <time itemprop="datePublished" datetime="2026-04-02T11:00:00Z">April 2, 2026</time>
            </article>
          </body>
        </html>
        """,
        "html.parser",
    )
    published = HTMLFetcher._extract_published_from_article_html(soup)
    assert published == "2026-04-02T11:00:00Z"


def test_extract_published_falls_back_to_time_text() -> None:
    soup = BeautifulSoup(
        """
        <html>
          <body>
            <article>
              <time>April 2, 2026</time>
            </article>
          </body>
        </html>
        """,
        "html.parser",
    )
    published = HTMLFetcher._extract_published_from_article_html(soup)
    assert published == "April 2, 2026"


def test_candidate_hrefs_extracts_script_embedded_urls() -> None:
    soup = BeautifulSoup(
        """
        <html>
          <body>
            <script>
              self.__next_f.push(["/blog/launch-post-1", "https://cohere.com/blog/launch-post-2"]);
            </script>
          </body>
        </html>
        """,
        "html.parser",
    )
    hrefs = HTMLFetcher._candidate_hrefs(
        soup,
        source={
            "url": "https://cohere.com/blog",
            "article_path_prefix": "/blog/",
        },
        max_items=5,
    )
    assert "https://cohere.com/blog/launch-post-1" in hrefs
    assert "https://cohere.com/blog/launch-post-2" in hrefs


def test_extract_published_from_text_month_day_year() -> None:
    text = "Latest News Mar 27, 2026 SAM 3.1: Faster and more accessible..."
    published = HTMLFetcher._extract_published_from_text(text)
    assert published == "Mar 27, 2026"
