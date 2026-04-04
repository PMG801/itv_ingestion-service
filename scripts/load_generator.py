"""
Load Generator - Integration test script for the ITV Ingestion Gateway.

Fires concurrent HTTP POST requests to /api/v1/ingest/{source}, simulating
all three data sources (valencia, galicia, catalunya) with randomised dummy
payloads, then reports throughput and latency metrics (incl. P95).

Usage
-----
    python scripts/load_generator.py --count 200 --sources valencia galicia --concurrency 30

Dependencies (no project imports required):
    pip install httpx
"""

import argparse
import asyncio
import logging
import random
import time
from collections import Counter
from collections.abc import Callable
from typing import Literal, TypedDict, TypeAlias, cast
from uuid import uuid4

import httpx

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("load_generator")

# ---------------------------------------------------------------------------
# Dummy payload generators
# Each returns a dict ready to be serialised as the JSON body of IngestRequest:
#   {"payload": <dict|str>, "format": "json"|"xml"}
# ---------------------------------------------------------------------------

_SPAIN_LAT = (36.0, 43.8)
_SPAIN_LON = (-9.3, 4.3)


class RequestBody(TypedDict):
    payload: dict[str, object] | str
    format: Literal["json", "xml"]


ResultOk: TypeAlias = tuple[Literal["ok"], str, bool, float]
ResultError: TypeAlias = tuple[Literal["error"], str, bool, str]
RequestResult: TypeAlias = ResultOk | ResultError


def _rand_postal() -> str:
    return f"{random.randint(1000, 52999):05d}"


def _rand_phone() -> str:
    return f"{random.randint(600_000_000, 999_999_999)}"


def _rand_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:6].upper()}"


def generate_valencia() -> RequestBody:
    """
    Mimics the Valencia API JSON structure (Spanish field names).

    Raw fixture reference: tests/fixtures/valencia_sample.json
        estaciones > codigo, nombre, direccion, poblacion, provincia,
                     codigo_postal, latitud, longitud, telefono, correo
    """
    return {
        "payload": {
            "estaciones": [
                {
                    "codigo": _rand_id("VAL"),
                    "nombre": f"ITV Valencia {uuid4().hex[:4].upper()}",
                    "direccion": f"Calle de la Industria {random.randint(1, 999)}",
                    "poblacion": random.choice(["Valencia", "Alicante", "Castellón"]),
                    "provincia": "Valencia",
                    "codigo_postal": _rand_postal(),
                    "latitud": round(random.uniform(*_SPAIN_LAT), 4),
                    "longitud": round(random.uniform(*_SPAIN_LON), 4),
                    "telefono": _rand_phone(),
                    "correo": f"itv_{uuid4().hex[:6]}@valencia.es",
                }
            ]
        },
        "format": "json",
    }


def generate_galicia() -> RequestBody:
    """
    Mimics the Galicia API JSON structure (Galician field names).

    Raw fixture reference: tests/fixtures/galicia_sample.json
        stations > id, nome, enderezo, concello, provincia, cp,
                   lat, lon, telefono, correo
    """
    return {
        "payload": {
            "stations": [
                {
                    "id": _rand_id("GAL"),
                    "nome": f"ITV Galicia {uuid4().hex[:4].upper()}",
                    "enderezo": f"Rúa da Industria {random.randint(1, 999)}",
                    "concello": random.choice(["Lugo", "Ourense", "Vigo", "A Coruña"]),
                    "provincia": random.choice(["Lugo", "Ourense", "Pontevedra", "La Coruña"]),
                    "cp": _rand_postal(),
                    "lat": round(random.uniform(41.8, 43.8), 4),
                    "lon": round(random.uniform(-9.3, -6.7), 4),
                    "telefono": _rand_phone(),
                    "correo": f"itv_{uuid4().hex[:6]}@galicia.gal",
                }
            ]
        },
        "format": "json",
    }


def generate_catalunya() -> RequestBody:
    """
    Mimics the Catalunya API XML structure (Catalan field names, comma as
    decimal separator in coordinates).

    Raw fixture reference: tests/fixtures/catalunya_sample.xml
        stations > station > id, nom, adreca, ciutat, provincia,
                             codi_postal, latitud, longitud, telefon, email
    """
    lat = round(random.uniform(40.5, 42.9), 4)
    lon = round(random.uniform(0.2, 3.3), 4)
    # Catalunya convention: comma as decimal separator
    lat_str = str(lat).replace(".", ",")
    lon_str = str(lon).replace(".", ",")

    xml_payload = (
        "<stations>"
        "<station>"
        f"<id>{_rand_id('BCN')}</id>"
        f"<nom>ITV Catalunya {uuid4().hex[:4].upper()}</nom>"
        f"<adreca>Carrer de la Industria {random.randint(1, 999)}</adreca>"
        f"<ciutat>{random.choice(['Barcelona', 'Girona', 'Lleida', 'Tarragona'])}</ciutat>"
        f"<provincia>Catalunya</provincia>"
        f"<codi_postal>{_rand_postal()}</codi_postal>"
        f"<latitud>{lat_str}</latitud>"
        f"<longitud>{lon_str}</longitud>"
        f"<telefon>{_rand_phone()}</telefon>"
        f"<email>itv_{uuid4().hex[:6]}@catalunya.cat</email>"
        "</station>"
        "</stations>"
    )
    return {
        "payload": xml_payload,
        "format": "xml",
    }


_GENERATORS = {
    "valencia": generate_valencia,
    "galicia": generate_galicia,
    "catalunya": generate_catalunya,
}


def _build_invalid_payload(source: str, body: RequestBody) -> RequestBody:
    """
    Build a source-specific payload that is accepted by Gateway but filtered
    by the normalizer transformer.

    The strategy is to keep payload shape valid and remove required station IDs,
    so transformers skip those entries and emit no normalized stations.
    """
    if source == "valencia":
        return {
            "payload": {
                "estaciones": [
                    {
                        "nombre": "ITV inválida VAL",
                        "direccion": "Calle Falsa 123",
                        "poblacion": "Valencia",
                        "provincia": "Valencia",
                        "codigo_postal": _rand_postal(),
                    }
                ]
            },
            "format": "json",
        }

    if source == "galicia":
        return {
            "payload": {
                "stations": [
                    {
                        "nome": "ITV inválida GAL",
                        "enderezo": "Rúa Falsa 123",
                        "concello": "Lugo",
                        "provincia": "Lugo",
                        "cp": _rand_postal(),
                    }
                ]
            },
            "format": "json",
        }

    if source == "catalunya":
        return {
            "payload": (
                "<stations>"
                "<station>"
                "<nom>ITV invàlida CAT</nom>"
                "<adreca>Carrer Fals 123</adreca>"
                "<ciutat>Barcelona</ciutat>"
                "<provincia>Catalunya</provincia>"
                "<codi_postal>08001</codi_postal>"
                "</station>"
                "</stations>"
            ),
            "format": "xml",
        }

    return body

# ---------------------------------------------------------------------------
# Async request sender
# ---------------------------------------------------------------------------


async def send_request(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    source: str,
    is_invalid: bool,
    url: str,
    body: RequestBody,
) -> RequestResult:
    """
    Send a single POST request under the semaphore.

    Returns
    -------
    ("ok", source, is_invalid, elapsed_seconds)   on HTTP 202
    ("error", source, is_invalid, "CODE Reason") on any other status code or connection error
    """
    async with semaphore:
        t0 = time.perf_counter()
        try:
            response = await client.post(url, json=body)
            elapsed = time.perf_counter() - t0

            if response.status_code == 202:
                return ("ok", source, is_invalid, elapsed)

            # Non-202: log a warning and return aggregatable error key
            reason = response.reason_phrase or "Unknown"
            error_key = f"{response.status_code} {reason}"
            logger.warning("Request failed: %s — %s", error_key, response.text[:120])
            return ("error", source, is_invalid, error_key)

        except httpx.RequestError as exc:
            error_key = f"ConnectionError: {type(exc).__name__}"
            logger.warning("Request error: %s", error_key)
            return ("error", source, is_invalid, error_key)

# ---------------------------------------------------------------------------
# Main coroutine
# ---------------------------------------------------------------------------


async def main(args: argparse.Namespace) -> None:
    if args.seed is not None:
        random.seed(args.seed)

    logger.info(
        "Starting load generator: count=%d, sources=%s, concurrency=%d, invalid_rate=%.2f, seed=%s, base_url=%s",
        args.count,
        args.sources,
        args.concurrency,
        args.invalid_rate,
        args.seed,
        args.url,
    )

    # Build task list — round-robin across requested sources
    tasks_meta: list[tuple[str, str, bool, RequestBody]] = []
    selected_sources = tuple(args.sources)
    sent_by_source: Counter[str] = Counter()
    invalid_by_source: Counter[str] = Counter()

    generators: dict[str, Callable[[], RequestBody]] = {
        source: _GENERATORS[source] for source in selected_sources
    }

    for i in range(args.count):
        source = selected_sources[i % len(selected_sources)]
        payload = generators[source]()
        is_invalid = random.random() < args.invalid_rate
        if is_invalid:
            payload = _build_invalid_payload(source, payload)

        url = f"{args.url.rstrip('/')}/{source}"
        tasks_meta.append((source, url, is_invalid, payload))
        sent_by_source[source] += 1
        if is_invalid:
            invalid_by_source[source] += 1

    # httpx client whose connection limits mirror the semaphore so the client
    # never becomes the bottleneck.
    limits = httpx.Limits(
        max_connections=args.concurrency,
        max_keepalive_connections=args.concurrency,
    )
    semaphore = asyncio.Semaphore(args.concurrency)

    async with httpx.AsyncClient(limits=limits, timeout=10.0) as client:
        coroutines = [
            send_request(client, semaphore, source, is_invalid, url, payload)
            for source, url, is_invalid, payload in tasks_meta
        ]

        wall_start = time.perf_counter()
        results = await asyncio.gather(*coroutines)
        wall_elapsed = time.perf_counter() - wall_start

    # ---------------------------------------------------------------------------
    # Aggregate results
    # ---------------------------------------------------------------------------
    latencies: list[float] = []
    error_counts: Counter[str] = Counter()
    accepted_by_source: Counter[str] = Counter()
    failed_by_source: Counter[str] = Counter()
    accepted_invalid = 0

    for result in results:
        status = result[0]
        if status == "ok":
            source = result[1]
            is_invalid = result[2]
            elapsed = cast(float, result[3])
            latencies.append(elapsed)  # seconds
            accepted_by_source[source] += 1
            if is_invalid:
                accepted_invalid += 1
        else:
            source = result[1]
            error_key = cast(str, result[3])
            error_counts[error_key] += 1
            failed_by_source[source] += 1

    total = len(results)
    successes = len(latencies)
    failures = total - successes
    throughput = total / wall_elapsed if wall_elapsed > 0 else float("inf")

    # Convert to milliseconds for display
    latencies_ms = [v * 1000 for v in latencies]

    # ---------------------------------------------------------------------------
    # Print summary
    # ---------------------------------------------------------------------------
    print()
    print("=" * 60)
    print("  LOAD GENERATOR — RESULTS")
    print("=" * 60)
    print(f"  Sent        : {total}")
    print(f"  Accepted    : {successes}  (HTTP 202)")
    print(f"  Failed      : {failures}")
    print(f"  Invalid sent: {sum(invalid_by_source.values())}  ({args.invalid_rate:.0%} target)")
    print(f"  Invalid 202 : {accepted_invalid}")
    print(f"  Elapsed     : {wall_elapsed:.2f}s")
    print(f"  Throughput  : {throughput:.1f} req/s")

    print()
    print("  Source breakdown:")
    for source in selected_sources:
        print(
            f"    {source:<10} sent={sent_by_source[source]:>4} "
            f"accepted={accepted_by_source[source]:>4} "
            f"failed={failed_by_source[source]:>4} "
            f"invalid={invalid_by_source[source]:>4}"
        )

    if latencies_ms:
        sorted_ms = sorted(latencies_ms)
        n = len(sorted_ms)
        avg_ms = sum(sorted_ms) / n
        p95_ms = sorted_ms[int(n * 0.95)]  # 95th percentile
        print()
        print("  Latency (ms) — successful requests only")
        print(f"    min  = {sorted_ms[0]:.1f}")
        print(f"    avg  = {avg_ms:.1f}")
        print(f"    P95  = {p95_ms:.1f}")
        print(f"    max  = {sorted_ms[-1]:.1f}")

    if error_counts:
        print()
        print("  Error breakdown:")
        for code, count in error_counts.most_common():
            print(f"    {code!r}: {count}")

    print("=" * 60)
    print()

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

VALID_SOURCES = list(_GENERATORS.keys())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Async load generator for the ITV Ingestion Gateway.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--count",
        type=int,
        default=100,
        metavar="N",
        help="Total number of requests to send.",
    )
    parser.add_argument(
        "--sources",
        nargs="+",
        default=VALID_SOURCES,
        choices=VALID_SOURCES,
        metavar="SOURCE",
        help=f"Data sources to simulate. Choices: {VALID_SOURCES}.",
    )
    parser.add_argument(
        "--url",
        type=str,
        default="http://localhost:8000/api/v1/ingest",
        metavar="URL",
        help="Base URL of the Gateway ingest endpoint (source appended as path segment).",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=20,
        metavar="N",
        help=(
            "Maximum simultaneous in-flight requests. "
            "Controls both asyncio.Semaphore and httpx connection pool size."
        ),
    )
    parser.add_argument(
        "--invalid-rate",
        type=float,
        default=0.0,
        metavar="RATE",
        help=(
            "Fraction of requests (0.0-1.0) sent with source-specific invalid payloads "
            "that should be filtered by the normalizer."
        ),
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        metavar="N",
        help="Optional random seed for reproducible load runs.",
    )
    args = parser.parse_args()

    if args.count <= 0:
        parser.error("--count must be > 0")
    if args.concurrency <= 0:
        parser.error("--concurrency must be > 0")
    if not (0.0 <= args.invalid_rate <= 1.0):
        parser.error("--invalid-rate must be between 0.0 and 1.0")

    return args


if __name__ == "__main__":
    asyncio.run(main(parse_args()))
