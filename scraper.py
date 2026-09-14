import ipaddress
import json
import re
import socket
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from product_model import ProductData

MAX_DOWNLOAD_BYTES = 2_000_000
MAX_REDIRECTS = 4
REQUEST_TIMEOUT_SECONDS = 15
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"
)


class ScraperError(Exception):
    pass


class PageUnavailableError(ScraperError):
    pass


class NetworkError(ScraperError):
    pass


def _clean_text(value, max_length):
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text[:max_length] if text else None


def _validate_public_url(url):
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ScraperError("Enter a valid http:// or https:// product URL.")

    hostname = parsed.hostname.lower()
    if hostname in {"localhost", "localhost.localdomain"}:
        raise ScraperError("Local addresses are not allowed.")

    try:
        addresses = socket.getaddrinfo(hostname, parsed.port or 443)
    except socket.gaierror as exc:
        raise NetworkError("The website address could not be resolved.") from exc

    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if not ip.is_global:
            raise ScraperError("Private or local network addresses are not allowed.")


def _download_html(url):
    current_url = url
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.8",
    }

    for _ in range(MAX_REDIRECTS + 1):
        _validate_public_url(current_url)
        try:
            response = requests.get(
                current_url,
                headers=headers,
                timeout=REQUEST_TIMEOUT_SECONDS,
                stream=True,
                allow_redirects=False,
            )
        except requests.exceptions.Timeout as exc:
            raise NetworkError("The product page request timed out.") from exc
        except requests.exceptions.ConnectionError as exc:
            raise NetworkError("Could not connect to the product website.") from exc
        except requests.exceptions.RequestException as exc:
            raise NetworkError("Network error while downloading the product page.") from exc

        if response.status_code in {301, 302, 303, 307, 308}:
            location = response.headers.get("Location")
            response.close()
            if not location:
                raise PageUnavailableError("The website returned an invalid redirect.")
            current_url = urljoin(current_url, location)
            continue

        if response.status_code in {401, 403, 429}:
            response.close()
            raise PageUnavailableError(
                "The page is unavailable or blocked by the website "
                f"(HTTP {response.status_code}). Try another product page."
            )
        if response.status_code == 404:
            response.close()
            raise PageUnavailableError("The product page was not found (HTTP 404).")
        if response.status_code >= 400:
            status = response.status_code
            response.close()
            raise PageUnavailableError(f"The product page returned HTTP {status}.")

        content_type = response.headers.get("Content-Type", "").lower()
        if "html" not in content_type and "xhtml" not in content_type:
            response.close()
            raise PageUnavailableError("The URL did not return an HTML page.")

        chunks = []
        downloaded = 0
        for chunk in response.iter_content(chunk_size=32_768):
            if not chunk:
                continue
            remaining = MAX_DOWNLOAD_BYTES - downloaded
            if remaining <= 0:
                break
            chunks.append(chunk[:remaining])
            downloaded += min(len(chunk), remaining)
            if downloaded >= MAX_DOWNLOAD_BYTES:
                break

        encoding = response.encoding or "utf-8"
        final_url = response.url or current_url
        response.close()
        return b"".join(chunks).decode(encoding, errors="replace"), final_url

    raise PageUnavailableError("Too many redirects while opening the product page.")


def _iter_json_ld_products(soup):
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = script.string or script.get_text(" ", strip=True)
        if not raw:
            continue
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            continue

        queue = parsed if isinstance(parsed, list) else [parsed]
        while queue:
            item = queue.pop(0)
            if not isinstance(item, dict):
                continue
            graph = item.get("@graph")
            if isinstance(graph, list):
                queue.extend(graph)
            item_type = item.get("@type")
            types = item_type if isinstance(item_type, list) else [item_type]
            if any(str(t).lower() == "product" for t in types if t):
                yield item


def _extract_from_json_ld(soup):
    for product in _iter_json_ld_products(soup):
        offers = product.get("offers") or {}
        if isinstance(offers, list):
            offers = next((offer for offer in offers if isinstance(offer, dict)), {})
        if not isinstance(offers, dict):
            offers = {}

        aggregate = product.get("aggregateRating") or {}
        if not isinstance(aggregate, dict):
            aggregate = {}

        price_value = offers.get("price") or offers.get("lowPrice")
        currency = offers.get("priceCurrency")
        price = None
        if price_value is not None:
            price = f"{price_value} {currency}".strip() if currency else str(price_value)

        return {
            "product_name": _clean_text(product.get("name"), 300),
            "price": _clean_text(price, 100),
            "description": _clean_text(product.get("description"), 4000),
            "review_rating": aggregate.get("ratingValue"),
        }
    return {}


def _meta_content(soup, *names):
    for name in names:
        tag = soup.find("meta", attrs={"property": name}) or soup.find("meta", attrs={"name": name})
        if tag and tag.get("content"):
            return tag.get("content")
    return None


def _first_text(soup, selectors, max_length):
    for selector in selectors:
        tag = soup.select_one(selector)
        if tag:
            value = tag.get("content") if tag.name == "meta" else tag.get_text(" ", strip=True)
            cleaned = _clean_text(value, max_length)
            if cleaned:
                return cleaned
    return None


def _fallback_extract(soup):
    name = _clean_text(_meta_content(soup, "og:title", "twitter:title"), 300)
    if not name:
        name = _first_text(
            soup,
            ["#productTitle", "[itemprop='name']", "[data-testid*='product-title']", "h1"],
            300,
        )

    amount = _meta_content(soup, "product:price:amount", "og:price:amount")
    currency = _meta_content(soup, "product:price:currency", "og:price:currency")
    price = None
    if amount:
        price = f"{amount} {currency}".strip() if currency else amount
    if not price:
        price = _first_text(
            soup,
            ["[itemprop='price']", ".a-price .a-offscreen", "[data-testid*='price']"],
            100,
        )

    description = _clean_text(
        _meta_content(soup, "description", "og:description", "twitter:description"),
        4000,
    )
    if not description:
        description = _first_text(
            soup,
            ["[itemprop='description']", "#productDescription", "[data-testid*='description']"],
            4000,
        )

    rating = None
    rating_tag = soup.select_one("[itemprop='ratingValue']")
    if rating_tag:
        rating = rating_tag.get("content") or rating_tag.get_text(" ", strip=True)
    if rating is None:
        page_text = soup.get_text(" ", strip=True)[:100_000]
        match = re.search(r"([0-5](?:\.\d+)?)\s*(?:out of\s*5|/\s*5)", page_text, flags=re.I)
        if match:
            rating = match.group(1)

    return {
        "product_name": name,
        "price": _clean_text(price, 100),
        "description": description,
        "review_rating": rating,
    }


def scrape_product(url):
    """Download a bounded amount of HTML and return validated ProductData."""
    html, final_url = _download_html(url.strip())
    soup = BeautifulSoup(html, "html.parser")

    structured = _extract_from_json_ld(soup)
    fallback = _fallback_extract(soup)

    merged = {
        "source_url": final_url,
        "product_name": structured.get("product_name") or fallback.get("product_name"),
        "price": structured.get("price") or fallback.get("price"),
        "description": structured.get("description") or fallback.get("description"),
        "review_rating": structured.get("review_rating") or fallback.get("review_rating"),
    }

    # ProductData validates types, lengths, URL format, and rating range.
    return ProductData.model_validate(merged)
