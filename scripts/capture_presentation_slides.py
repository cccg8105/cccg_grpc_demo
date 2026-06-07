#!/usr/bin/env python3
"""Capture reveal.js slides and detect basic visual issues."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HTML = ROOT / "presentation" / "grpc-intro.html"
OUT_BASE = ROOT / "presentation" / "screenshots"


def slug(text: str, max_len: int = 40) -> str:
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    text = re.sub(r"[\s_]+", "-", text.strip().lower())
    return (text[:max_len] or "slide").strip("-")


def get_slide_map(page) -> list[dict]:
    return page.evaluate(
        """() => {
        const stacks = Array.from(document.querySelectorAll('.reveal .slides > section'));
        const map = [];
        stacks.forEach((stack, h) => {
            const nested = stack.querySelectorAll(':scope > section');
            if (nested.length === 0) {
                map.push({ h, v: 0 });
            } else {
                nested.forEach((_, v) => map.push({ h, v }));
            }
        });
        return map;
    }"""
    )


def patch_html_navigation(html_path: Path) -> None:
    text = html_path.read_text(encoding="utf-8")
    patched = text.replace("navigationMode: 'default'", "navigationMode: 'vertical'")
    if patched != text:
        html_path.write_text(patched, encoding="utf-8")


def analyze_slide(page, h: int, v: int) -> dict:
    page.evaluate(
        """() => {
        document.querySelectorAll('.fragment:not(.visible)').forEach(
            el => el.classList.add('visible')
        );
    }"""
    )
    return page.evaluate(
        """([h, v]) => {
        const section = Reveal.getSlide(h, v);
        if (!section) {
            return { title: '', charCount: 0, isEmpty: true, hasOverflow: false,
                     brokenTitle: false, mermaidPending: false };
        }
        const clone = section.cloneNode(true);
        clone.querySelectorAll('aside.notes').forEach(n => n.remove());
        const heading = clone.querySelector('h1, h2');
        const title = heading ? heading.innerText.trim() : '';
        const visibleText = clone.innerText.replace(/\\s+/g, ' ').trim();
        const limit = document.querySelector('.reveal').getBoundingClientRect().bottom - 36;
        let hasOverflow = false;
        clone.querySelectorAll('h1,h2,h3,p,li,table,pre,.mermaid,.callout,.columns').forEach(el => {
            const r = el.getBoundingClientRect();
            if (r.height > 8 && r.bottom > limit) hasOverflow = true;
        });
        const brokenTitle = /\\{\\.[^}]+\\}/.test(title) || /scrollable/i.test(title);
        const pending = section.querySelector('pre.mermaid:not(:has(svg))');
        return {
            title,
            charCount: visibleText.length,
            isEmpty: visibleText.length < 40,
            hasOverflow,
            brokenTitle,
            mermaidPending: !!pending,
        };
    }""",
        [h, v],
    )


def capture_slides(html_path: Path, out_dir: Path) -> list[dict]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise SystemExit(
            "Playwright no instalado. Ejecuta: pip install playwright && "
            "playwright install chromium"
        ) from exc

    out_dir.mkdir(parents=True, exist_ok=True)
    reports: list[dict] = []

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1050, "height": 700})
        page.goto(html_path.as_uri(), wait_until="networkidle")
        page.wait_for_timeout(3000)

        page.wait_for_function(
            "() => window.Reveal && Reveal.isReady && Reveal.isReady()"
        )

        slide_map = get_slide_map(page)

        for entry in slide_map:
            h, v = entry["h"], entry["v"]
            page.evaluate(f"() => Reveal.slide({h}, {v})")
            page.wait_for_timeout(600)

            info = analyze_slide(page, h, v)
            title = info.get("title") or f"slide-h{h}-v{v}"
            fname = f"h{h:02d}-v{v:02d}-{slug(title)}.png"
            fpath = out_dir / fname
            page.screenshot(path=str(fpath), full_page=False)

            reports.append({
                "hIndex": h,
                "vIndex": v,
                "title": title,
                "path": str(fpath.relative_to(ROOT)),
                **info,
            })

        browser.close()

    return reports


def summarize(reports: list[dict]) -> dict:
    main = [r for r in reports if r["vIndex"] == 0]
    branches = [r for r in reports if r["vIndex"] > 0]
    branch_overflow = [r for r in branches if r.get("hasOverflow")]

    return {
        "totalSlides": len(reports),
        "emptySlides": [r for r in reports if r.get("isEmpty")],
        "overflowMain": [r for r in main if r.get("hasOverflow")],
        "overflowBranches": branch_overflow,
        "brokenTitles": [r for r in reports if r.get("brokenTitle")],
        "mermaidPending": [r for r in reports if r.get("mermaidPending")],
        "passed": (
            not any(r.get("isEmpty") for r in reports)
            and not any(r.get("brokenTitle") for r in reports)
            and not any(r.get("mermaidPending") for r in reports)
            and not any(r.get("hasOverflow") for r in main)
            and len(branch_overflow) <= 1
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture presentation slides")
    parser.add_argument("--iter", type=int, default=1, help="Iteration number")
    parser.add_argument(
        "--html",
        type=Path,
        default=HTML,
        help="Path to rendered HTML",
    )
    args = parser.parse_args()

    if not args.html.exists():
        print(f"HTML no encontrado: {args.html}", file=sys.stderr)
        print("Ejecuta primero: quarto render presentation/grpc-intro.qmd", file=sys.stderr)
        return 1

    patch_html_navigation(args.html.resolve())
    out_dir = OUT_BASE / f"iter-{args.iter}"
    reports = capture_slides(args.html.resolve(), out_dir)
    summary = summarize(reports)

    report_path = out_dir / "report.json"
    report_path.write_text(
        json.dumps({"summary": summary, "slides": reports}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"Capturas: {out_dir} ({len(reports)} slides)")
    print(f"Reporte:  {report_path}")
    print(f"Passed:   {summary['passed']}")

    if summary["emptySlides"]:
        print(f"  Vacias: {len(summary['emptySlides'])}")
        for r in summary["emptySlides"]:
            print(f"    - h{r['hIndex']} v{r['vIndex']}: {r['title']!r}")
    if summary["overflowMain"]:
        print(f"  Overflow (main): {len(summary['overflowMain'])}")
        for r in summary["overflowMain"]:
            print(f"    - h{r['hIndex']} v{r['vIndex']}: {r['title']}")
    if summary["overflowBranches"]:
        print(f"  Overflow (branch): {len(summary['overflowBranches'])}")
        for r in summary["overflowBranches"]:
            print(f"    - h{r['hIndex']} v{r['vIndex']}: {r['title']}")
    if summary["brokenTitles"]:
        print(f"  Titulos rotos: {len(summary['brokenTitles'])}")
    if summary["mermaidPending"]:
        print(f"  Mermaid pendiente: {len(summary['mermaidPending'])}")

    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
