from __future__ import annotations

import json
import re
from html import escape
from urllib.parse import urlparse

from config.settings import SOURCE_REGISTRY_PATH
from models.pipeline_types import ClusterRow
from services.clustering.embedding_service import EmbeddingService, _normalize_search_text
from services.digest.digest_html_template import render_digest_document
from services.digest.summary_utils import summarize_for_digest
from utils.json_utils import read_json
from utils.logging_utils import get_logger

_SOURCE_SHOW_MORE_LIMIT = 8
_logger = get_logger(__name__)


class DigestHtmlRenderer:
    @staticmethod
    def _source_counts(clusters: list[ClusterRow]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for cluster in clusters:
            for source_id in cluster.get("source_ids") or []:
                if source_id:
                    counts[source_id] = counts.get(source_id, 0) + 1
        return counts

    @staticmethod
    def _source_layout(source_filters_html: str) -> tuple[str, str]:
        controls_grid_class = "controls-grid" + (" controls-grid--with-sources" if source_filters_html else "")
        sources_column_html = (
            f'        <div class="controls-column--right">\n{source_filters_html}        </div>\n'
            if source_filters_html
            else ""
        )
        return controls_grid_class, sources_column_html

    @staticmethod
    def _searchable_title_for_cluster(cluster: ClusterRow) -> str:
        return (cluster.get("title") or "Untitled").strip()

    @staticmethod
    def _plain_summary_for_search(cluster: ClusterRow) -> str:
        """Plain text aligned with the digest card summary (summarized, no markdown)."""
        summarized = summarize_for_digest((cluster.get("summary") or "").strip())
        if not summarized:
            return ""
        s = summarized
        s = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r"\1", s)
        s = re.sub(r"\*\*(.+?)\*\*", r"\1", s)
        s = re.sub(r"__(.+?)__", r"\1", s)
        s = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"\1", s)
        s = re.sub(r"(?<!_)_(?!_)(.+?)(?<!_)_(?!_)", r"\1", s)
        s = re.sub(r"\s+", " ", s).strip()
        return s

    @staticmethod
    def _search_index_script(
        clusters: list[ClusterRow],
        *,
        embedding_service: EmbeddingService | None = None,
    ) -> str:
        titles = [DigestHtmlRenderer._searchable_title_for_cluster(c) for c in clusters]
        summaries = [DigestHtmlRenderer._plain_summary_for_search(c) for c in clusters]
        texts = [_normalize_search_text(f"{t}\n{s}") for t, s in zip(titles, summaries)]
        embeddings: list[list[float]] = []
        dim = 0
        try:
            es = embedding_service or EmbeddingService()
            raw = [f"{t}\n{s}" for t, s in zip(titles, summaries)]
            arr = es.embed_plain_texts(raw)
            embeddings = arr.tolist()
            dim = int(arr.shape[1]) if arr.size else 0
        except Exception:
            _logger.warning(
                "Digest search index embedding failed; output uses keyword matching only.",
                exc_info=True,
            )
        payload = {
            "texts": texts,
            "titles": titles,
            "summaries": summaries,
            "embeddings": embeddings,
            "dim": dim,
        }
        return json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")

    @staticmethod
    def render(
        title: str,
        run_date: str,
        time_window: str,
        clusters: list[ClusterRow],
        *,
        embedding_service: EmbeddingService | None = None,
    ) -> str:
        search_json = DigestHtmlRenderer._search_index_script(clusters, embedding_service=embedding_service)
        cards = "\n".join(
            [DigestHtmlRenderer._cluster_card(cluster, idx) for idx, cluster in enumerate(clusters)],
        )
        counts = DigestHtmlRenderer._source_counts(clusters)
        registry = DigestHtmlRenderer._load_registry_by_id()
        all_source_ids = sorted(
            counts.keys(),
            key=lambda s: DigestHtmlRenderer._display_name_for_source(s, registry.get(s, {})).lower(),
        )
        source_filters_html = DigestHtmlRenderer._source_filters_section(all_source_ids, counts, registry)
        controls_grid_class, sources_column_html = DigestHtmlRenderer._source_layout(source_filters_html)
        return render_digest_document(
            title=title,
            run_date=run_date,
            time_window=time_window,
            controls_grid_class=controls_grid_class,
            sources_column_html=sources_column_html,
            search_json=search_json,
            cards_html=cards,
        )

    @staticmethod
    def _load_registry_by_id() -> dict[str, dict]:
        try:
            data = read_json(SOURCE_REGISTRY_PATH)
            sources = data.get("sources") if isinstance(data, dict) else []
            if not isinstance(sources, list):
                return {}
            return {str(s["source_id"]): s for s in sources if isinstance(s, dict) and s.get("source_id")}
        except Exception:
            return {}

    @staticmethod
    def _display_name_for_source(source_id: str, source_row: dict) -> str:
        name = source_row.get("name")
        if isinstance(name, str) and name.strip():
            return name.strip()
        return source_id.replace("_", " ")

    @staticmethod
    def _favicon_url_for_source(source_row: dict) -> str:
        u = source_row.get("feed_url") or source_row.get("url") or source_row.get("api_endpoint") or ""
        if not isinstance(u, str) or not u.strip():
            return ""
        netloc = urlparse(u.strip()).netloc
        if not netloc:
            return ""
        raw_url = f"https://www.google.com/s2/favicons?domain={netloc}&sz=32"
        return escape(raw_url, quote=True)

    @staticmethod
    def _source_filters_section(
        source_ids: list[str],
        counts: dict[str, int],
        registry_by_id: dict[str, dict],
    ) -> str:
        if not source_ids:
            return ""
        rows: list[str] = []
        show_more = len(source_ids) > _SOURCE_SHOW_MORE_LIMIT
        for idx, sid in enumerate(source_ids):
            row_meta = registry_by_id.get(sid) or {}
            label = DigestHtmlRenderer._display_name_for_source(sid, row_meta)
            fav = DigestHtmlRenderer._favicon_url_for_source(row_meta)
            n = int(counts.get(sid, 0))
            extra_class = " source-row--extra" if show_more and idx >= _SOURCE_SHOW_MORE_LIMIT else ""
            fav_html = (
                f'<img class="source-favicon" src="{fav}" alt="" width="20" height="20" loading="lazy" />'
                if fav
                else '<span class="source-favicon" style="display:inline-block;width:20px;height:20px;border-radius:4px;background:#e5e7eb;flex-shrink:0;"></span>'
            )
            rows.append(
                "              <li"
                f' class="source-row{extra_class}">\n'
                "                <label>\n"
                f'                  <input type="checkbox" class="source-filter" value="{escape(sid)}" checked="checked" />\n'
                f"                  {fav_html}\n"
                f'                  <span class="source-label-text">{escape(label)}</span>\n'
                f'                  <span class="source-count">({n})</span>\n'
                "                </label>\n"
                "              </li>"
            )
        rows_html = "\n".join(rows)
        show_more_btn = ""
        if show_more:
            show_more_btn = (
                '              <button type="button" id="source_show_more" class="source-show-more">'
                "&rsaquo; Show more sources</button>\n"
            )
        return (
            '          <aside class="controls-group sources-facet">\n'
            '            <details class="sources-details" open>\n'
            '              <summary class="sources-summary">\n'
            "                <span>Sources</span>\n"
            '                <span class="sources-chevron" aria-hidden="true">&#9650;</span>\n'
            "              </summary>\n"
            '              <p class="sources-hint">Only sources with at least one matching cluster are listed. Counts follow search, dates, and score filters. Uncheck to narrow further.</p>\n'
            '              <div class="source-list-wrap">\n'
            '                <div class="source-row source-row--select-all">\n'
            '                  <label for="source_select_all">\n'
            '                    <input type="checkbox" id="source_select_all" checked="checked" />\n'
            '                    <span class="source-label-text">All sources</span>\n'
            "                  </label>\n"
            "                </div>\n"
            f'                <ul class="source-list">\n{rows_html}\n                </ul>\n'
            "              </div>\n"
            f"{show_more_btn}"
            "            </details>\n"
            "          </aside>\n"
        )

    @staticmethod
    def _cluster_card(cluster: ClusterRow, card_index: int = 0) -> str:
        title = escape((cluster.get("title") or "Untitled").strip())
        summary = DigestHtmlRenderer._render_inline_markdown(
            summarize_for_digest((cluster.get("summary") or "").strip())
        )
        links = cluster.get("links") or []
        earliest_published_date = cluster.get("earliest_published_date") or cluster.get("earliest_item_date")
        score = cluster.get("score") or {}
        source_ids = cluster.get("source_ids") or []
        sources_attr = escape(" ".join(sorted(source_ids)))

        meta_parts = []
        if earliest_published_date:
            meta_parts.append(f"Date: {escape(str(earliest_published_date))}")
        if score:
            meta_parts.append(
                "Scores: "
                f"relevance {escape(str(score.get('mean_relevance', 0)))}, "
                f"importance {escape(str(score.get('mean_importance', 0)))}, "
                f"novelty {escape(str(score.get('mean_novelty', 0)))}, "
                f"trust {escape(str(score.get('mean_trust', 0)))}, "
                f"composed {escape(str(score.get('mean_composed', 0)))}"
            )
        meta_line = " | ".join(meta_parts)

        refs_html = ""
        if links:
            refs_li = "\n".join(
                [
                    f'          <li><a href="{escape(link)}" target="_blank" rel="noreferrer">{escape(link)}</a></li>'
                    for link in links
                ]
            )
            refs_html = (
                '      <section class="refs">\n'
                '        <p class="refs-title">References</p>\n'
                "        <ul>\n"
                f"{refs_li}\n"
                "        </ul>\n"
                "      </section>\n"
            )

        return (
            '    <article class="card">\n'
            f"      <h2>{title}</h2>\n"
            f'      <p class="card-meta">{meta_line}</p>\n'
            f'      <p class="summary">{summary}</p>\n'
            f"{refs_html}"
            "    </article>"
        ).replace(
            '<article class="card">',
            (
                '<article class="card"'
                f' data-card-idx="{int(card_index)}"'
                f' data-title="{escape((cluster.get("title") or "Untitled").strip())}"'
                f' data-date="{escape(str(earliest_published_date or ""))}"'
                f' data-sources="{sources_attr}"'
                f' data-relevance="{escape(str(score.get("mean_relevance", 0)))}"'
                f' data-importance="{escape(str(score.get("mean_importance", 0)))}"'
                f' data-novelty="{escape(str(score.get("mean_novelty", 0)))}"'
                f' data-trust="{escape(str(score.get("mean_trust", 0)))}"'
                f' data-composed="{escape(str(score.get("mean_composed", 0)))}"'
                ">"
            ),
            1,
        )

    @staticmethod
    def _render_inline_markdown(text: str) -> str:
        # Support markdown links, bold/italic, and raw URLs.
        link_pattern = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")
        placeholders: list[str] = []

        def link_repl(match: re.Match) -> str:
            label = escape(match.group(1).strip())
            url = escape(match.group(2).strip())
            placeholders.append(f'<a href="{url}" target="_blank" rel="noreferrer">{label}</a>')
            return f"@@LINK{len(placeholders) - 1}@@"

        text = link_pattern.sub(link_repl, text)
        escaped = escape(text)
        escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
        escaped = re.sub(r"__(.+?)__", r"<strong>\1</strong>", escaped)
        escaped = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", escaped)
        escaped = re.sub(r"(?<!_)_(?!_)(.+?)(?<!_)_(?!_)", r"<em>\1</em>", escaped)

        pattern = re.compile(r"(https?://[^\s<]+)")
        out: list[str] = []
        last = 0
        for match in pattern.finditer(escaped):
            out.append(escaped[last : match.start()])
            raw_url = match.group(1).strip()
            url = escape(raw_url)
            out.append(f'<a href="{url}" target="_blank" rel="noreferrer">{escape(raw_url)}</a>')
            last = match.end()
        out.append(escaped[last:])
        rendered = "".join(out)
        for idx, html in enumerate(placeholders):
            rendered = rendered.replace(f"@@LINK{idx}@@", html)
        return rendered
