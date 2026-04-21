from __future__ import annotations

from html import escape

from services.digest.digest_html_assets import DIGEST_PAGE_SCRIPT, DIGEST_PAGE_STYLE


def render_digest_document(
    *,
    title: str,
    run_date: str,
    time_window: str,
    controls_grid_class: str,
    sources_column_html: str,
    search_json: str,
    cards_html: str,
) -> str:
    return (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '  <meta charset="utf-8" />\n'
        '  <meta name="viewport" content="width=device-width, initial-scale=1" />\n'
        f"  <title>{escape(title)}</title>\n"
        "  <style>\n"
        f"{DIGEST_PAGE_STYLE}"
        "  </style>\n"
        "</head>\n"
        "<body>\n"
        '  <main class="page">\n'
        '    <header class="header">\n'
        f'      <h1 class="title">{escape(title)}</h1>\n'
        f'      <p class="meta">Run date: {escape(run_date)}</p>\n'
        f'      <p class="meta">Time window: {escape(time_window)}</p>\n'
        "    </header>\n"
        '    <section class="controls">\n'
        '      <div class="controls-toolbar">\n'
        '        <form id="search_form" class="controls-search-form" role="search">\n'
        '          <label class="visually-hidden" for="search_q">Search digest</label>\n'
        '          <input id="search_q" name="q" type="text" placeholder="Type terms, then Enter or Search" autocomplete="off" enterkeyhint="search" />\n'
        '          <button type="submit" id="search_btn">Search</button>\n'
        "        </form>\n"
        '        <div class="controls-toolbar-meta">\n'
        '          <span id="result_count" class="result-count"></span>\n'
        '          <button id="reset_filters" type="button">Reset</button>\n'
        "        </div>\n"
        '        <p id="search_semantic_hint" class="search-hint" style="grid-column:1/-1;margin:8px 0 0;" hidden></p>\n'
        "      </div>\n"
        '      <details class="controls-filters-details">\n'
        '        <summary class="controls-filters-summary">\n'
        "          <span>Filters, sort &amp; sources</span>\n"
        '          <span class="summary-chev" aria-hidden="true">&#9660;</span>\n'
        "        </summary>\n"
        '        <div class="controls-filters-inner">\n'
        f'          <div class="{controls_grid_class}">\n'
        '            <div class="controls-main">\n'
        '              <div class="controls-panel">\n'
        '                <div class="controls-group">\n'
        '                  <p class="controls-section-title">Filter</p>\n'
        '                  <p class="controls-subtitle">Date range</p>\n'
        '                  <div class="controls-fields controls-fields--dates">\n'
        '                    <div><label for="date_from">From</label><input id="date_from" type="date" /></div>\n'
        '                    <div><label for="date_to">To</label><input id="date_to" type="date" /></div>\n'
        "                  </div>\n"
        '                  <p class="controls-subtitle">Minimum scores [0, 1]</p>\n'
        '                  <div class="controls-fields controls-fields--scores">\n'
        '                    <div><label for="min_relevance">Relevance</label><input id="min_relevance" type="number" min="0" max="1" step="0.01" value="0" /></div>\n'
        '                    <div><label for="min_importance">Importance</label><input id="min_importance" type="number" min="0" max="1" step="0.01" value="0" /></div>\n'
        '                    <div><label for="min_novelty">Novelty</label><input id="min_novelty" type="number" min="0" max="1" step="0.01" value="0" /></div>\n'
        '                    <div><label for="min_trust">Trust</label><input id="min_trust" type="number" min="0" max="1" step="0.01" value="0" /></div>\n'
        '                    <div><label for="min_composed">Composed</label><input id="min_composed" type="number" min="0" max="1" step="0.01" value="0" /></div>\n'
        "                  </div>\n"
        "                </div>\n"
        '                <hr class="controls-block-sep" />\n'
        '                <div class="controls-group">\n'
        '                  <p class="controls-section-title">Sort</p>\n'
        '                  <div class="controls-fields controls-fields--sort">\n'
        '                    <div><label for="sort_by">Sort by</label><select id="sort_by"><option value="date">Date</option><option value="relevance">Relevance</option><option value="importance">Importance</option><option value="novelty">Novelty</option><option value="trust">Trust</option><option value="composed" selected>Composed</option><option value="title">Title</option></select></div>\n'
        '                    <div><label for="sort_order">Order</label><select id="sort_order"><option value="desc" selected>High to low</option><option value="asc">Low to high</option></select></div>\n'
        "                  </div>\n"
        "                </div>\n"
        "              </div>\n"
        "            </div>\n"
        f"{sources_column_html}"
        "          </div>\n"
        "        </div>\n"
        "      </details>\n"
        "    </section>\n"
        f'    <script type="application/json" id="digest-search-index">{search_json}</script>\n'
        '    <section id="cards_container">\n'
        f"{cards_html}\n"
        "    </section>\n"
        "  </main>\n"
        "  <script>\n"
        f"{DIGEST_PAGE_SCRIPT}"
        "  </script>\n"
        "</body>\n"
        "</html>\n"
    )
