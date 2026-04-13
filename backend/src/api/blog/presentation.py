import html
import re

from api.blog.storage import get_asset_url


def normalize_markdown_for_web(run_id: str, markdown_text: str) -> str:
    normalized = markdown_text.replace("](images/", f"]({get_asset_url(run_id, 'images/')}")
    normalized = normalized.replace("](./images/", f"]({get_asset_url(run_id, 'images/')}")
    return normalized


def render_markdown_html(run_id: str, markdown_text: str) -> str:
    import markdown as markdown_lib

    normalized = normalize_markdown_for_web(run_id, markdown_text)
    body = markdown_lib.markdown(
        normalized,
        extensions=["fenced_code", "tables", "sane_lists", "toc"],
    )

    title_match = re.search(r"^#\s+(.+)$", markdown_text, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else "Blog Preview"
    escaped_title = html.escape(title)

    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{escaped_title}</title>
    <style>
      :root {{
        --bg: #f7f4ec;
        --paper: #fffdf8;
        --ink: #1b1a17;
        --muted: #655f52;
        --line: #ded6c6;
        --accent: #b84c2a;
        --code-bg: #f1ece1;
      }}
      * {{ box-sizing: border-box; }}
      body {{
        margin: 0;
        background:
          radial-gradient(circle at top left, rgba(184, 76, 42, 0.08), transparent 28rem),
          linear-gradient(180deg, #f2ecdf 0%, var(--bg) 48%, #efe7d7 100%);
        color: var(--ink);
        font-family: "Iowan Old Style", "Palatino Linotype", "Book Antiqua", Georgia, serif;
        line-height: 1.75;
      }}
      .page {{
        max-width: 960px;
        margin: 0 auto;
        padding: 32px 20px 64px;
      }}
      .article {{
        background: color-mix(in srgb, var(--paper) 92%, white 8%);
        border: 1px solid rgba(107, 95, 76, 0.18);
        border-radius: 28px;
        box-shadow: 0 24px 80px rgba(65, 49, 29, 0.08);
        overflow: hidden;
      }}
      .hero {{
        padding: 48px 48px 24px;
        border-bottom: 1px solid var(--line);
        background:
          radial-gradient(circle at top right, rgba(184, 76, 42, 0.14), transparent 18rem),
          linear-gradient(135deg, rgba(255,255,255,0.92), rgba(247,244,236,0.94));
      }}
      .hero p {{
        margin: 0;
        color: var(--muted);
        font-size: 0.95rem;
        letter-spacing: 0.04em;
        text-transform: uppercase;
      }}
      .content {{
        padding: 20px 48px 48px;
      }}
      h1, h2, h3 {{
        line-height: 1.15;
        letter-spacing: -0.02em;
      }}
      h1 {{
        margin: 0;
        font-size: clamp(2.4rem, 4vw, 4rem);
      }}
      h2 {{
        margin-top: 2.4rem;
        margin-bottom: 1rem;
        font-size: clamp(1.6rem, 2vw, 2.2rem);
        color: #241d13;
      }}
      h3 {{
        margin-top: 1.8rem;
        margin-bottom: 0.75rem;
        font-size: 1.3rem;
      }}
      p, li {{
        font-size: 1.08rem;
      }}
      a {{
        color: var(--accent);
      }}
      img {{
        display: block;
        width: 100%;
        margin: 2rem auto 0.75rem;
        border-radius: 20px;
        border: 1px solid rgba(52, 45, 35, 0.12);
        box-shadow: 0 20px 50px rgba(39, 29, 20, 0.12);
        background: linear-gradient(180deg, #f4efe6, #ebe3d3);
      }}
      em {{
        display: block;
        color: var(--muted);
        font-size: 0.96rem;
        margin-bottom: 1.4rem;
      }}
      pre, code {{
        font-family: "SFMono-Regular", "Menlo", "Monaco", monospace;
      }}
      pre {{
        background: var(--code-bg);
        padding: 16px;
        border-radius: 16px;
        overflow-x: auto;
        border: 1px solid rgba(79, 65, 44, 0.1);
      }}
      code {{
        background: var(--code-bg);
        padding: 0.18rem 0.35rem;
        border-radius: 6px;
      }}
      blockquote {{
        margin: 1.5rem 0;
        padding: 0.2rem 1rem;
        border-left: 4px solid rgba(184, 76, 42, 0.4);
        color: #4b4336;
        background: rgba(184, 76, 42, 0.04);
        border-radius: 0 12px 12px 0;
      }}
      @media (max-width: 720px) {{
        .hero {{
          padding: 32px 24px 20px;
        }}
        .content {{
          padding: 16px 24px 32px;
        }}
      }}
    </style>
  </head>
  <body>
    <main class="page">
      <article class="article">
        <header class="hero">
          <p>Generated Blog Preview</p>
          <h1>{escaped_title}</h1>
        </header>
        <section class="content">{body}</section>
      </article>
    </main>
  </body>
</html>
"""
