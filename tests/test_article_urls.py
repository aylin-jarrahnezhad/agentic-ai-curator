from utils.text import is_useful_article_url


def test_rejects_corporate_about_pages():
    assert is_useful_article_url("https://deepmind.google/about") is False
    assert is_useful_article_url("https://example.com/careers") is False


def test_accepts_typical_article_paths():
    assert is_useful_article_url("https://deepmind.google/discover/blog/some-post-title") is True
    assert is_useful_article_url("https://example.com/news/2026/ai-update") is True
