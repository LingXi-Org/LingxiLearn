"""No-key, SSRF-aware web.search/web.fetch tools for lecture-hook."""

from __future__ import annotations

import asyncio
import html
import ipaddress
import json
import re
import socket
from html.parser import HTMLParser
from typing import Any, cast
from urllib.parse import parse_qs, urlencode, urljoin, urlparse

import httpx
from lingxigraph import tool

from ..config import Settings

MAX_RESULTS = 8
MAX_REDIRECTS = 3


class _TextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.title: list[str] = []
        self.links: list[tuple[str, str]] = []
        self._skip = 0
        self._in_title = False
        self._active_link: int | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript", "template", "svg"}:
            self._skip += 1
        if tag == "title":
            self._in_title = True
        if tag == "a" and self._skip == 0:
            href = dict(attrs).get("href")
            if href:
                self.links.append((href, ""))
                self._active_link = len(self.links) - 1

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "title":
            self._in_title = False
        if tag == "a":
            self._active_link = None
        if tag in {"script", "style", "noscript", "template", "svg"}:
            self._skip = max(0, self._skip - 1)

    def handle_data(self, data: str) -> None:
        value = " ".join(data.split())
        if not value or self._skip:
            return
        self.parts.append(value)
        if self._in_title:
            self.title.append(value)
        if self._active_link is not None:
            href, label = self.links[self._active_link]
            self.links[self._active_link] = (href, f"{label} {value}".strip())


async def _assert_public_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("only public http/https URLs are allowed")
    host = parsed.hostname.lower().rstrip(".")
    if host in {"localhost", "metadata.google.internal"}:
        raise ValueError("local and metadata hosts are not allowed")
    try:
        addresses = await asyncio.to_thread(socket.getaddrinfo, host, None, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise ValueError(f"host lookup failed: {host}") from exc
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise ValueError("private or non-routable hosts are not allowed")


async def _get_public(url: str, settings: Settings) -> tuple[str, httpx.Response]:
    current = url
    async with httpx.AsyncClient(
        timeout=settings.agent_web_timeout,
        follow_redirects=False,
        headers={"User-Agent": "LingxiLearn/agent-research"},
    ) as client:
        for _ in range(MAX_REDIRECTS + 1):
            await _assert_public_url(current)
            response = await client.get(current)
            if response.status_code not in {301, 302, 303, 307, 308}:
                response.raise_for_status()
                if len(response.content) > settings.agent_max_html_bytes:
                    raise ValueError("web response exceeds configured size limit")
                return current, response
            location = response.headers.get("location")
            if not location:
                break
            current = urljoin(current, location)
    raise ValueError("too many redirects")


def build_web_tools(settings: Settings) -> list[Any]:
    async def web_search(query: str, domains: str = "", freshness: str = "") -> str:
        """Search the public web and return title, URL, snippet and domain."""

        if not query.strip():
            raise ValueError("query must not be empty")
        params = {"q": query.strip(), "kl": "wt-wt"}
        if domains.strip():
            sites = " ".join(
                f"site:{item.strip()}" for item in domains.split(",") if item.strip()
            )
            params["q"] += " " + sites
        search_url = settings.agent_search_url + (
            "&" if "?" in settings.agent_search_url else "?"
        ) + urlencode(params)
        final_url, response = await _get_public(
            search_url,
            settings,
        )
        parser = _TextParser()
        parser.feed(response.text)
        results: list[dict[str, str]] = []
        for href, label in parser.links:
            if "duckduckgo.com/l/?" in href:
                query_values = parse_qs(urlparse(href).query)
                href = query_values.get("uddg", [href])[0]
            absolute = urljoin(final_url, html.unescape(href))
            parsed = urlparse(absolute)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                continue
            if any(item["url"] == absolute for item in results):
                continue
            results.append(
                {
                    "title": label or absolute,
                    "url": absolute,
                    "snippet": label or "",
                    "source": parsed.netloc,
                    "published_at": "",
                }
            )
            if len(results) >= MAX_RESULTS:
                break
        return json.dumps(
            {"query": query, "freshness": freshness, "results": results},
            ensure_ascii=False,
        )

    async def web_fetch(url: str) -> str:
        """Fetch a public page and return title, final URL and cleaned text."""

        final_url, response = await _get_public(url, settings)
        parser = _TextParser()
        parser.feed(response.text)
        text = re.sub(r"\s+", " ", " ".join(parser.parts)).strip()
        return json.dumps(
            {
                "url": final_url,
                "title": " ".join(parser.title).strip() or final_url,
                "content": text[: settings.agent_max_html_bytes],
                "published_at": response.headers.get("last-modified", ""),
            },
            ensure_ascii=False,
        )

    return [
        cast(Any, tool(name="web_search", timeout=settings.agent_web_timeout))(web_search),
        cast(Any, tool(name="web_fetch", timeout=settings.agent_web_timeout))(web_fetch),
    ]
