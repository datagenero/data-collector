"""
SAIJ (Sistema Argentino de Información Jurídica) scraper.

This script automates the collection of legal rulings ("Fallos") from the SAIJ
website (https://www.saij.gob.ar/) using a headless Chromium browser via Playwright.

Workflow:
    1. Navigate to the SAIJ homepage.
    2. Select "Fallo" in the document-type dropdown and submit the search form.
    3. Paginate through the search-result listing, collecting a URL for each result.
    4. For every URL, open a dedicated browser tab and extract:
         - title      : the main heading of the ruling (h1.p-titulo)
         - sumario    : the plain-text summary (stripped of HTML tags)
         - full_text_links : /descarga-archivo hrefs of the document parts inside #partes
    5. For each ruling, download every file listed in full_text_links into
       <output_dir>/<ruling_id>_<index>.<ext> using Playwright's download API.
    6. Save each ruling's metadata as <output_dir>/<ruling_id>.json.

Result pages are processed in parallel (one browser tab per URL on the same
listing page) to speed up collection. Downloads are performed sequentially per
ruling to avoid overwhelming the server.

Usage:
    python scrape.py --output-dir ./data [--limit-pages N]

Arguments:
    --output-dir    Directory where downloaded files and metadata are written (required).
    --limit-pages   Stop after scraping this many listing pages (default: no limit).
"""

import argparse
import asyncio
import json
import os
import re
import httpx
from playwright.async_api import async_playwright


def strip_html(text):
    """Remove HTML tags and collapse whitespace from an HTML string."""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", text)).strip()


async def process_page(browser, href):
    """Open *href* in a new tab and extract structured data for a single ruling.

    Args:
        browser: A Playwright Browser instance used to open a new page.
        href:    Full URL of the ruling detail page.

    Returns:
        A dict with the following keys:
            - ``href``            : the original URL.
            - ``title``           : plain-text content of the h1.p-titulo element.
            - ``sumario``         : plain-text summary stripped of HTML tags.
            - ``full_text_links`` : list of hrefs extracted from anchors inside
                                    the ``#partes`` div that start with
                                    ``/descarga-archivo`` (document-part downloads).
    """
    page = await browser.new_page()
    try:
        await page.goto(href)
        await page.wait_for_load_state("networkidle")

        title = await page.locator("h1.p-titulo").inner_text()

        sumario_html = await page.locator(
            "#texto-sumario p.p-descriptor-sumario"
        ).inner_html()
        sumario = strip_html(sumario_html)

        # Get all href from all <a> elements inside div#partes
        full_text_links = []
        try:
            # Wait a bit longer for the div to appear since it loads in stages
            await page.wait_for_selector("#partes", state="attached", timeout=10000)

            # Wait a bit more to ensure links inside have loaded
            # await asyncio.sleep(1)

            # Get all <a> elements inside the partes div
            partes_links = page.locator("#partes a")
            links_count = await partes_links.count()

            # Extract href from each link, keeping only document-download URLs
            for i in range(links_count):
                link_href = await partes_links.nth(i).get_attribute("href")
                if link_href and link_href.startswith("/descarga-archivo"):
                    full_text_links.append(link_href)

            print(f"Extracted {len(full_text_links)} valid hrefs from #partes")

        except Exception as e:
            print(f"Error getting links from #partes for {href}: {e}")
            full_text_links = []

        return {
            "href": href,
            "title": title,
            "sumario": sumario,
            "full_text_links": full_text_links,
        }
    finally:
        await page.close()


def _ruling_id(title):
    """Derive a filesystem-safe ID from a ruling's title.

    Strips punctuation characters (``,`` ``.`` ``/`` ``;``) then replaces
    runs of whitespace with underscores.

    Example: ``"Fallo: García, J. c/ Estado"`` → ``"Fallo:_García_J_c_Estado"``
    """
    clean = re.sub(r"[,./;]", "", title)
    return re.sub(r"\s+", "_", clean).strip("_")


async def _download_one(client, ruling_id, index, download_url, output_dir):
    """Download a single file via *client* and save it to *output_dir*.

    The filename is ``<ruling_id>_<index>.<ext>`` where ``ext`` is taken from
    the ``Content-Disposition`` header when available, falling back to the last
    segment of the URL path, and finally ``.bin``.

    Args:
        client:       An ``httpx.AsyncClient`` instance.
        ruling_id:    Filesystem-safe identifier for the ruling.
        index:        Zero-based position of this link in ``full_text_links``.
        download_url: Fully-resolved URL to fetch.
        output_dir:   Directory where the file will be saved.
    """
    print(f"Downloading {download_url} ...")
    try:
        async with client.stream("GET", download_url) as response:
            response.raise_for_status()

            # Derive extension from Content-Disposition, then URL path, then default
            disposition = response.headers.get("content-disposition", "")
            cd_match = re.search(r'filename="?([^";]+)"?', disposition)
            if cd_match:
                ext = os.path.splitext(cd_match.group(1))[-1]
            else:
                ext = os.path.splitext(download_url.rsplit("/", 1)[-1])[-1] or ".bin"

            dest = os.path.join(output_dir, f"{ruling_id}_{index}{ext}")
            with open(dest, "wb") as f:
                async for chunk in response.aiter_bytes():
                    f.write(chunk)

        print(f"Saved {dest}")
    except Exception as e:
        print(f"Error downloading {download_url}: {e}")


async def download_files(base_url, result, output_dir):
    """Download all files listed in *result['full_text_links']* to *output_dir*.

    Each link in ``full_text_links`` is a relative path resolved against
    *base_url*. All files for a ruling are fetched concurrently using
    ``httpx.AsyncClient``.

    Each file is saved as ``<ruling_id>_<index>.<ext>``, where:
        - ``ruling_id`` is derived from the ruling's title via :func:`_ruling_id`.
        - ``index``     is the zero-based position in ``full_text_links``.
        - ``ext``       is inferred from the ``Content-Disposition`` header,
                        the URL path, or defaults to ``.bin``.

    Args:
        base_url:   Base URL of the SAIJ website (used to resolve relative hrefs).
        result:     Dict returned by :func:`process_page` for a single ruling.
        output_dir: Directory where downloaded files will be saved.
    """
    ruling_id = _ruling_id(result["title"])
    async with httpx.AsyncClient(follow_redirects=True, timeout=60) as client:
        await asyncio.gather(
            *(
                _download_one(
                    client,
                    ruling_id,
                    index,
                    base_url.rstrip("/") + rel_link,
                    output_dir,
                )
                for index, rel_link in enumerate(result["full_text_links"])
            )
        )


async def collect_hrefs(page, browser, base_url, limit_pages, output_dir):
    """Paginate through SAIJ search results, download files, and save metadata.

    For every listing page the function:
        1. Collects all result-item URLs from ``div.resultado-busqueda li.result-item a``.
        2. Processes each URL in parallel via :func:`process_page`.
        3. For each result, downloads all files in ``full_text_links`` via
           :func:`download_files` and writes a ``<ruling_id>.json`` metadata file.
        4. Clicks the "next page" button (``#paginador-boton-siguiente``) and repeats
           until there are no more pages or *limit_pages* has been reached.

    Args:
        page:        The Playwright Page currently showing the search-results listing.
        browser:     A Playwright Browser used to open detail pages in parallel.
        base_url:    Base URL of the SAIJ website (used to resolve download links).
        limit_pages: Maximum number of listing pages to process, or ``None`` for no limit.
        output_dir:  Directory where downloaded files and metadata are saved.
    """
    current_page = 0

    while limit_pages is None or current_page < limit_pages:
        current_page += 1
        print(f"\n--- Page {current_page} ---")

        links = page.locator("div.resultado-busqueda li.result-item a")
        count = await links.count()

        page_hrefs = await asyncio.gather(
            *(links.nth(i).get_attribute("href") for i in range(count))
        )
        valid_hrefs = []
        for i, href in enumerate(page_hrefs):
            if not href or not href.startswith("http"):
                print(
                    f"Error getting items from page {current_page} at index {i}: {href}"
                )
                continue
            valid_hrefs.append(href)

        # Process all hrefs on this page in parallel
        page_results = await asyncio.gather(
            *(process_page(browser, href) for href in valid_hrefs)
        )

        # Download files and write metadata for each result
        for result in page_results:
            ruling_id = _ruling_id(result["title"])

            # Download all document files for this ruling
            await download_files(base_url, result, output_dir)

            # Save metadata as a JSON file alongside the downloads
            meta_path = os.path.join(output_dir, f"{ruling_id}.json")
            with open(meta_path, "w", encoding="utf-8") as mf:
                json.dump(result, mf, ensure_ascii=False, indent=2)
            print(f"Metadata saved to {meta_path}")

        # Try to go to the next page
        next_button = page.locator("#paginador #paginador-boton-siguiente")
        if await next_button.is_visible():
            await next_button.click()
            await page.wait_for_load_state("networkidle")
        else:
            print("No more pages.")
            break

    print(f"All results saved to {output_dir}")


async def main(url, limit_pages, output_dir):
    """Entry point for the SAIJ scraper.

    Launches a headless Chromium browser, navigates to *url*, selects the
    "Fallo" document type, triggers the search, and delegates pagination,
    file downloads, and metadata saving to :func:`collect_hrefs`.

    Args:
        url:         Base URL of the SAIJ website (also used to resolve download links).
        limit_pages: Maximum number of listing pages to scrape, or ``None`` for no limit.
        output_dir:  Directory where downloaded files and metadata will be saved
                     (created if absent).
    """
    os.makedirs(output_dir, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        print(f"Navigating to {url}...")
        await page.goto(url)
        await page.wait_for_load_state("networkidle")

        print("Page loaded successfully!")

        # Select "Fallo" in the tipoDocumento dropdown and wait for the form to update
        print("Selecting 'Fallo' in tipoDocumento...")
        select_locator = page.locator("#tipoDocumento")
        await select_locator.select_option(label="Fallo")
        # Wait for the search button to become visible (client-side form update,
        # no network request)
        await page.locator("#btn-search-fallo").wait_for(state="visible", timeout=10000)
        print("Form updated after selecting 'Fallo'.")

        # Click the search button
        print("Clicking search button...")
        await page.click("#btn-search-fallo")
        await page.wait_for_load_state("networkidle")
        print("Search results loaded!")

        await collect_hrefs(page, browser, url, limit_pages, output_dir)

        await browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape SAIJ documents")
    parser.add_argument(
        "--limit-pages",
        type=int,
        default=None,
        help="Maximum number of pages to scrape. No limit if not specified.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        required=True,
        help="Output directory to save the collected files.",
    )
    args = parser.parse_args()

    url = "https://www.saij.gob.ar/"
    asyncio.run(main(url, args.limit_pages, args.output_dir))
