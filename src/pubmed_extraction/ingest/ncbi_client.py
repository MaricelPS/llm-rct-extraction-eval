"""Thin client for NCBI E-utilities with rate limiting and retries."""

import threading
import time
from collections.abc import Iterator

import httpx
from lxml import etree
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from pubmed_extraction.settings import settings

EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


class RateLimiter:
    """Simple thread-safe limiter enforcing a minimum interval between calls."""

    def __init__(self, rate_per_sec: float) -> None:
        self._interval = 1.0 / rate_per_sec
        self._lock = threading.Lock()
        self._last = 0.0

    def wait(self) -> None:
        with self._lock:
            elapsed = time.monotonic() - self._last
            if elapsed < self._interval:
                time.sleep(self._interval - elapsed)
            self._last = time.monotonic()


class NCBIClient:
    def __init__(self, timeout: float = 30.0) -> None:
        self._http = httpx.Client(base_url=EUTILS_BASE, timeout=timeout)
        self._limiter = RateLimiter(settings.ncbi_rate_limit)

    def _base_params(self) -> dict[str, str]:
        params = {"tool": settings.ncbi_tool, "email": settings.ncbi_email}
        if settings.ncbi_api_key:
            params["api_key"] = settings.ncbi_api_key
        return params

    @retry(
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TransportError)),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        stop=stop_after_attempt(5),
    )
    def _get(self, endpoint: str, params: dict[str, str]) -> bytes:
        self._limiter.wait()
        response = self._http.get(endpoint, params={**self._base_params(), **params})
        response.raise_for_status()
        return response.content

    def search_pubmed(self, term: str, retmax: int = 500) -> list[str]:
        """Return PMIDs matching a PubMed query."""
        content = self._get("esearch.fcgi", {"db": "pubmed", "term": term, "retmax": str(retmax)})
        root = etree.fromstring(content)
        return root.xpath("//IdList/Id/text()")

    def pmids_to_pmcids(self, pmids: list[str], batch_size: int = 200) -> dict[str, str]:
        """Map PMIDs to PMCIDs using PubMed records. PMIDs without PMC copy are dropped."""
        mapping: dict[str, str] = {}
        for i in range(0, len(pmids), batch_size):
            batch = pmids[i : i + batch_size]
            content = self._get(
                "efetch.fcgi", {"db": "pubmed", "id": ",".join(batch), "retmode": "xml"}
            )
            root = etree.fromstring(content)
            for article in root.xpath("//PubmedArticle"):
                pmid = article.xpath("string(.//MedlineCitation/PMID)")
                pmcid = article.xpath("string(.//ArticleIdList/ArticleId[@IdType='pmc'])")
                if pmid and pmcid:
                    mapping[pmid] = pmcid
        return mapping

    def fetch_jats(self, pmcid: str) -> bytes:
        """Fetch full-text JATS XML for a single PMC article."""
        numeric_id = pmcid.removeprefix("PMC")
        return self._get("efetch.fcgi", {"db": "pmc", "id": numeric_id, "retmode": "xml"})

    def iter_jats(self, pmcids: list[str]) -> Iterator[tuple[str, bytes]]:
        for pmcid in pmcids:
            yield pmcid, self.fetch_jats(pmcid)