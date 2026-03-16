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


def _rand_postal() -> str:
    return f"{random.randint(1000, 52999):05d}"


def _rand_phone() -> str:
    return f"{random.randint(600_000_000, 999_999_999)}"


def _rand_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:6].upper()}"


def generate_valencia() -> dict:
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


def generate_galicia() -> dict:
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
                    "provincia": random.choice(["Lugo", "Ourense", "Pontevedra", "A Coruña"]),
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


def generate_catalunya() -> dict:
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

# ---------------------------------------------------------------------------
# Async request sender
# ---------------------------------------------------------------------------


async def send_request(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    url: str,
    body: dict,
) -> tuple[str, float | str]:
    """
    Send a single POST request under the semaphore.

    Returns
    -------
    ("ok", elapsed_seconds)   on HTTP 202
    ("error", "CODE Reason")  on any other status code or connection error
    """
    async with semaphore:
        t0 = time.perf_counter()
        try:
            response = await client.post(url, json=body)
            elapsed = time.perf_counter() - t0

            if response.status_code == 202:
                return ("ok", elapsed)

            # Non-202: log a warning and return aggregatable error key
            reason = response.reason_phrase or "Unknown"
            error_key = f"{response.status_code} {reason}"
            logger.warning("Request failed: %s — %s", error_key, response.text[:120])
            return ("error", error_key)

        except httpx.RequestError as exc:
            elapsed = time.perf_counter() - t0
            error_key = f"ConnectionError: {type(exc).__name__}"
            logger.warning("Request error: %s", error_key)
            return ("error", error_key)

# ---------------------------------------------------------------------------
# Main coroutine
# ---------------------------------------------------------------------------


async def main(args: argparse.Namespace) -> None:
    logger.info(
        "Starting load generator: count=%d, sources=%s, concurrency=%d, base_url=%s",
        args.count,
        args.sources,
        args.concurrency,
        args.url,
    )

    # Build task list — round-robin across requested sources
    tasks_meta: list[tuple[str, dict]] = []
    sources_cycle = args.sources
    for i in range(args.count):
        source = sources_cycle[i % len(sources_cycle)]
        payload = _GENERATORS[source]()
        url = f"{args.url.rstrip('/')}/{source}"
        tasks_meta.append((url, payload))

    # httpx client whose connection limits mirror the semaphore so the client
    # never becomes the bottleneck.
    limits = httpx.Limits(
        max_connections=args.concurrency,
        max_keepalive_connections=args.concurrency,
    )
    semaphore = asyncio.Semaphore(args.concurrency)

    async with httpx.AsyncClient(limits=limits, timeout=10.0) as client:
        coroutines = [
            send_request(client, semaphore, url, payload)
            for url, payload in tasks_meta
        ]

        wall_start = time.perf_counter()
        results = await asyncio.gather(*coroutines)
        wall_elapsed = time.perf_counter() - wall_start

    # ---------------------------------------------------------------------------
    # Aggregate results
    # ---------------------------------------------------------------------------
    latencies: list[float] = []
    error_counts: Counter[str] = Counter()

    for status, value in results:
        if status == "ok":
            latencies.append(value)  # seconds
        else:
            error_counts[value] += 1

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
    print(f"  Elapsed     : {wall_elapsed:.2f}s")
    print(f"  Throughput  : {throughput:.1f} req/s")

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
    return parser.parse_args()


if __name__ == "__main__":
    asyncio.run(main(parse_args()))
