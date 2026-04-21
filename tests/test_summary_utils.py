from services.digest.summary_utils import normalize_summary_text, summarize_for_digest


def test_normalize_summary_text_removes_known_boilerplate() -> None:
    raw = (
        "Thank you for visiting nature.com. You are using a browser version with limited support for CSS."
        " To obtain the best experience, we recommend you use a more up to date browser."
        " Publish AI, ML & data-science insights to a global community of data professionals. "
        " Real content remains."
    )
    normalized = normalize_summary_text(raw)
    assert "Publish AI, ML" not in normalized
    assert "Real content remains." in normalized


def test_summarize_for_digest_limits_to_two_paragraphs() -> None:
    text = "Sentence one. Sentence two. Sentence three. " "Sentence four. Sentence five. Sentence six. Sentence seven."
    summary = summarize_for_digest(text)
    paragraphs = summary.split("\n\n")
    assert len(paragraphs) == 2
    assert "Sentence seven" not in summary
