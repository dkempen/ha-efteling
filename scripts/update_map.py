"""Generate the seasonal Efteling park maps from the map tile service."""  # noqa: INP001

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import math
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from typing import cast

from PIL import Image

_LOGGER = logging.getLogger("generate_park_map")

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIRECTORY = REPOSITORY_ROOT / "images" / "map"
DEFAULT_DEBUG_OUTPUT_DIRECTORY = DEFAULT_OUTPUT_DIRECTORY

TILE_URL_TEMPLATE = (
    "https://www.efteling.com/mapbox/style/{season}/tiles/{zoom}/{x}/{y}.webp"
)

SEASONS = ("summer", "winter")
ZOOM_LEVEL = 18
TILE_SIZE = 512
TILE_GRID_SIZE = 24
FULL_MAP_SIZE = TILE_GRID_SIZE * TILE_SIZE
TILE_ORIGIN_X = 134736
TILE_ORIGIN_Y = 86993

# Coordinates are left, top, right, bottom on the canvas after a 90-degree
# counterclockwise rotation of the complete 24-by-24 tile canvas.
ROTATED_CROP = (2570, 3530, 7260, 8220)

JPEG_QUALITY = 90
JPEG_SUBSAMPLING = 0
JPEG_OPTIMIZE = True
JPEG_PROGRESSIVE = True
WHITE_RGBA = (255, 255, 255, 255)
WHITE_RGB = (255, 255, 255)

MANIFEST_FILENAME = "manifest.json"
DEFAULT_WORKERS = 8
DEFAULT_TIMEOUT_SECONDS = 30
DEFAULT_RETRIES = 3
RETRY_BACKOFF_SECONDS = 1.0
MAX_RETRY_BACKOFF_SECONDS = 8.0
MIN_WORKERS = 1
MIN_TIMEOUT_SECONDS = 0.0
MIN_RETRIES = 1

# Retry HTTP 429 and server errors; other HTTP errors are permanent failures.
RETRYABLE_HTTP_STATUS_CODES = frozenset({429, 500, 502, 503, 504})


class MapGenerationError(Exception):
    """Represent an error that prevents a map from being generated."""


@dataclass(frozen=True, slots=True)
class GeneratorOptions:
    """Store settings shared by the tile download and map generation steps."""

    output_directory: Path
    debug_output_directory: Path
    workers: int
    timeout: float
    retries: int
    full_size: bool


@dataclass(frozen=True, slots=True)
class TileDownloadAttempt:
    """Hold the result of one tile request attempt."""

    image: Image.Image | None
    error: OSError | None
    retryable: bool


@dataclass(frozen=True, slots=True)
class GeneratedMap:
    """Hold the generated map hash, JPEG data, and optional full-size image."""

    pixel_sha256: str
    jpeg_bytes: bytes
    full_size_image: Image.Image | None


@dataclass(frozen=True, slots=True)
class SeasonResult:
    """Describe whether the visible pixels changed for one seasonal map."""

    season: str
    pixel_changed: bool


def parse_arguments(arguments: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Download, stitch, crop, and save the Efteling park maps."
    )
    parser.add_argument(
        "--season",
        choices=("both", *SEASONS),
        default="both",
        help="Which seasonal map to generate (default: both).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIRECTORY,
        help="Directory for map images and manifest.json.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=DEFAULT_WORKERS,
        help=f"Maximum concurrent tile downloads (default: {DEFAULT_WORKERS}).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=(
            f"Tile download timeout in seconds (default: {DEFAULT_TIMEOUT_SECONDS})."
        ),
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=DEFAULT_RETRIES,
        help=f"Maximum attempts per tile (default: {DEFAULT_RETRIES}).",
    )
    parser.add_argument(
        "--full-size",
        action="store_true",
        help=(
            "Also download all 576 tiles and save the uncropped, rotated "
            "12288x12288 JPEG map for crop debugging."
        ),
    )
    parser.add_argument(
        "--debug-output-dir",
        type=Path,
        default=DEFAULT_DEBUG_OUTPUT_DIRECTORY,
        help=(
            "Directory for full-size debug JPEGs "
            f"(default: {DEFAULT_DEBUG_OUTPUT_DIRECTORY})."
        ),
    )
    return parser.parse_args(arguments)


def configure_logging() -> None:
    """Configure readable console logging."""
    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        level=logging.INFO,
    )


def get_source_crop() -> tuple[int, int, int, int]:
    """Convert the crop after rotation to coordinates before rotation."""
    left, top, right, bottom = ROTATED_CROP
    return FULL_MAP_SIZE - bottom, left, FULL_MAP_SIZE - top, right


def get_geographic_coordinates(
    pixel_x: int,
    pixel_y: int,
) -> dict[str, float]:
    """Convert coordinates on the source tile canvas to latitude and longitude."""
    world_pixel_size = TILE_SIZE * (2**ZOOM_LEVEL)

    world_pixel_x = TILE_ORIGIN_X * TILE_SIZE + pixel_x
    world_pixel_y = TILE_ORIGIN_Y * TILE_SIZE + pixel_y

    longitude = world_pixel_x / world_pixel_size * 360.0 - 180.0
    mercator_y = math.pi * (1.0 - 2.0 * world_pixel_y / world_pixel_size)
    latitude = math.degrees(math.atan(math.sinh(mercator_y)))

    return {
        "latitude": round(latitude, 8),
        "longitude": round(longitude, 8),
    }


def get_map_bounds() -> dict[str, float]:
    """Return the minimum and maximum geographic coordinates of the map."""
    source_left, source_top, source_right, source_bottom = get_source_crop()
    top_left = get_geographic_coordinates(source_right, source_top)
    bottom_right = get_geographic_coordinates(source_left, source_bottom)
    return {
        "min_latitude": bottom_right["latitude"],
        "max_latitude": top_left["latitude"],
        "min_longitude": bottom_right["longitude"],
        "max_longitude": top_left["longitude"],
    }


def get_required_tile_coordinates() -> tuple[tuple[int, int], ...]:
    """Return only the tiles intersecting the final cropped map."""
    source_left, source_top, source_right, source_bottom = get_source_crop()
    min_tile_x = source_left // TILE_SIZE
    max_tile_x = (source_right - 1) // TILE_SIZE
    min_tile_y = source_top // TILE_SIZE
    max_tile_y = (source_bottom - 1) // TILE_SIZE

    return tuple(
        (TILE_ORIGIN_X + tile_x, TILE_ORIGIN_Y + tile_y)
        for tile_y in range(min_tile_y, max_tile_y + 1)
        for tile_x in range(min_tile_x, max_tile_x + 1)
    )


def get_all_tile_coordinates() -> tuple[tuple[int, int], ...]:
    """Return all 576 coordinates for a full-size debug map."""
    return tuple(
        (TILE_ORIGIN_X + tile_x, TILE_ORIGIN_Y + tile_y)
        for tile_y in range(TILE_GRID_SIZE)
        for tile_x in range(TILE_GRID_SIZE)
    )


def decode_tile(data: bytes, x: int, y: int) -> Image.Image:
    """Decode a WebP tile to opaque RGB pixels."""
    with Image.open(BytesIO(data)) as source_image:
        source_image.load()
        if source_image.size != (TILE_SIZE, TILE_SIZE):
            message = (
                f"Unexpected tile dimensions for {x}/{y}: "
                f"{source_image.width}x{source_image.height}; "
                f"expected {TILE_SIZE}x{TILE_SIZE}."
            )
            raise MapGenerationError(message)

        rgba_image = source_image.convert("RGBA")

    background = Image.new("RGBA", rgba_image.size, WHITE_RGBA)
    return Image.alpha_composite(background, rgba_image).convert("RGB")


def fetch_tile_attempt(
    url: str,
    x: int,
    y: int,
    timeout: float,
) -> TileDownloadAttempt:
    """Perform one tile request and return either the image or its error."""
    if not url.startswith(("http:", "https:")):
        message = f"Unsupported URL scheme for tile {x}/{y}."
        raise MapGenerationError(message)

    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:  # noqa: S310
            data = response.read()
    except urllib.error.HTTPError as error:
        return TileDownloadAttempt(
            image=None,
            error=error,
            retryable=error.code in RETRYABLE_HTTP_STATUS_CODES,
        )
    except OSError as error:
        return TileDownloadAttempt(image=None, error=error, retryable=True)

    return TileDownloadAttempt(
        image=decode_tile(data, x, y),
        error=None,
        retryable=False,
    )


def download_tile(
    season: str,
    x: int,
    y: int,
    options: GeneratorOptions,
) -> Image.Image:
    """Download and decode a tile, retrying transient request failures."""
    url = TILE_URL_TEMPLATE.format(
        season=season,
        zoom=ZOOM_LEVEL,
        x=x,
        y=y,
    )

    for attempt in range(1, options.retries + 1):
        result = fetch_tile_attempt(url, x, y, options.timeout)
        if result.image is not None:
            return result.image

        error = result.error
        if error is None:
            message = f"Tile request for {season} tile {x}/{y} returned no result."
            raise MapGenerationError(message)
        if not result.retryable or attempt == options.retries:
            message = f"Failed to download {season} tile {x}/{y}: {error}."
            raise MapGenerationError(message) from error

        _LOGGER.warning(
            "Error downloading %s tile %s/%s (attempt %s/%s): %s",
            season,
            x,
            y,
            attempt,
            options.retries,
            error,
        )
        delay = min(
            RETRY_BACKOFF_SECONDS * (2 ** (attempt - 1)),
            MAX_RETRY_BACKOFF_SECONDS,
        )
        time.sleep(delay)

    message = f"Failed to download {season} tile {x}/{y}."
    raise MapGenerationError(message)


def download_tiles(
    season: str,
    coordinates: tuple[tuple[int, int], ...],
    options: GeneratorOptions,
) -> dict[tuple[int, int], Image.Image]:
    """Download all requested map tiles concurrently."""
    downloaded: dict[tuple[int, int], Image.Image] = {}

    with ThreadPoolExecutor(max_workers=options.workers) as executor:
        futures = {
            executor.submit(download_tile, season, x, y, options): (x, y)
            for x, y in coordinates
        }

        for future in as_completed(futures):
            x, y = futures[future]
            downloaded[(x, y)] = future.result()
            _LOGGER.info(
                "Downloaded %s tile %s/%s (%s/%s).",
                season,
                x,
                y,
                len(downloaded),
                len(coordinates),
            )

    return downloaded


def create_cropped_map(
    season: str,
    downloaded_tiles: dict[tuple[int, int], Image.Image],
    *,
    full_size: bool,
) -> tuple[Image.Image, Image.Image | None]:
    """Stitch tiles, optionally retain the full map, then apply the crop."""
    source_crop = get_source_crop()

    if full_size:
        mosaic_origin_x = TILE_ORIGIN_X
        mosaic_origin_y = TILE_ORIGIN_Y
        mosaic_size = (FULL_MAP_SIZE, FULL_MAP_SIZE)
    else:
        coordinates = tuple(downloaded_tiles)
        min_tile_x = min(x for x, _ in coordinates)
        max_tile_x = max(x for x, _ in coordinates)
        min_tile_y = min(y for _, y in coordinates)
        max_tile_y = max(y for _, y in coordinates)
        mosaic_origin_x = min_tile_x
        mosaic_origin_y = min_tile_y
        mosaic_size = (
            (max_tile_x - min_tile_x + 1) * TILE_SIZE,
            (max_tile_y - min_tile_y + 1) * TILE_SIZE,
        )

    mosaic = Image.new("RGB", mosaic_size, WHITE_RGB)
    for (x, y), tile_image in downloaded_tiles.items():
        offset = (
            (x - mosaic_origin_x) * TILE_SIZE,
            (y - mosaic_origin_y) * TILE_SIZE,
        )
        mosaic.paste(tile_image, offset)

    # Release the decoded tile images before allocating the rotated full canvas.
    downloaded_tiles.clear()

    if full_size:
        full_size_image = mosaic.transpose(Image.Transpose.ROTATE_90)
        del mosaic
        cropped = full_size_image.crop(ROTATED_CROP)
    else:
        full_size_image = None
        source_tile_origin_x = (mosaic_origin_x - TILE_ORIGIN_X) * TILE_SIZE
        source_tile_origin_y = (mosaic_origin_y - TILE_ORIGIN_Y) * TILE_SIZE
        source_left, source_top, source_right, source_bottom = source_crop
        crop_box = (
            source_left - source_tile_origin_x,
            source_top - source_tile_origin_y,
            source_right - source_tile_origin_x,
            source_bottom - source_tile_origin_y,
        )
        cropped = mosaic.crop(crop_box).transpose(Image.Transpose.ROTATE_90)
        del mosaic

    expected_size = (
        ROTATED_CROP[2] - ROTATED_CROP[0],
        ROTATED_CROP[3] - ROTATED_CROP[1],
    )
    if cropped.size != expected_size:
        message = (
            f"Unexpected output dimensions for {season}: {cropped.width}x"
            f"{cropped.height}; expected {expected_size[0]}x{expected_size[1]}."
        )
        raise MapGenerationError(message)

    return cropped, full_size_image


def generate_map(
    season: str,
    coordinates: tuple[tuple[int, int], ...],
    options: GeneratorOptions,
) -> GeneratedMap:
    """Download tiles and generate one seasonal JPEG map."""
    _LOGGER.info("Generating %s map from %s tiles.", season, len(coordinates))
    downloaded_tiles = download_tiles(season, coordinates, options)
    image, full_size_image = create_cropped_map(
        season,
        downloaded_tiles,
        full_size=options.full_size,
    )

    try:
        pixel_sha256 = hashlib.sha256(image.tobytes()).hexdigest()
        jpeg_buffer = BytesIO()
        image.save(
            jpeg_buffer,
            format="JPEG",
            quality=JPEG_QUALITY,
            subsampling=JPEG_SUBSAMPLING,
            optimize=JPEG_OPTIMIZE,
            progressive=JPEG_PROGRESSIVE,
        )
        jpeg_bytes = jpeg_buffer.getvalue()
    finally:
        image.close()

    return GeneratedMap(
        pixel_sha256=pixel_sha256,
        jpeg_bytes=jpeg_bytes,
        full_size_image=full_size_image,
    )


def read_manifest(path: Path) -> dict[str, object]:
    """Read the current manifest, including the previous wrapped format."""
    if not path.exists():
        return {}

    try:
        manifest: object = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        message = f"Existing map manifest is not valid JSON: {path}"
        raise MapGenerationError(message) from error

    if not isinstance(manifest, dict):
        message = "The map manifest root must be a JSON object."
        raise MapGenerationError(message)

    # Retain the previous hashes and timestamps when migrating from the old format.
    if "maps" in manifest:
        maps = manifest["maps"]
        if not isinstance(maps, dict):
            message = "The legacy map manifest 'maps' value must be an object."
            raise MapGenerationError(message)
        return cast("dict[str, object]", maps)

    return cast("dict[str, object]", manifest)


def write_bytes_atomically(path: Path, content: bytes) -> None:
    """Write bytes to a temporary file and atomically replace the destination."""
    temporary_path = path.with_name(f".{path.name}.tmp")
    try:
        temporary_path.write_bytes(content)
        temporary_path.replace(path)
    finally:
        temporary_path.unlink(missing_ok=True)


def write_text_atomically(path: Path, content: str) -> None:
    """Write UTF-8 text to a temporary file and atomically replace the target."""
    temporary_path = path.with_name(f".{path.name}.tmp")
    try:
        temporary_path.write_text(content, encoding="utf-8", newline="\n")
        temporary_path.replace(path)
    finally:
        temporary_path.unlink(missing_ok=True)


def get_utc_timestamp() -> str:
    """Return the current UTC timestamp in ISO 8601 format using a Z suffix."""
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def update_season(
    season: str,
    previous_maps: dict[str, object],
    coordinates: tuple[tuple[int, int], ...],
    options: GeneratorOptions,
) -> tuple[dict[str, object], SeasonResult]:
    """Generate and save a map, updating its compact manifest entry."""
    generated = generate_map(season, coordinates, options)
    previous = previous_maps.get(season, {})
    if not isinstance(previous, dict):
        previous = {}

    previous_pixel_hash = previous.get("pixel_sha256")
    pixel_changed = previous_pixel_hash != generated.pixel_sha256

    image_path = options.output_directory / f"{season}.jpg"
    write_bytes_atomically(image_path, generated.jpeg_bytes)

    previous_updated_at = previous.get("updated_at")
    updated_at = (
        get_utc_timestamp()
        if pixel_changed or not isinstance(previous_updated_at, str)
        else previous_updated_at
    )

    if options.full_size and generated.full_size_image is not None:
        options.debug_output_directory.mkdir(parents=True, exist_ok=True)
        debug_path = options.debug_output_directory / f"{season}-full.jpg"
        temporary_path = debug_path.with_name(f".{debug_path.name}.tmp")

        try:
            generated.full_size_image.save(
                temporary_path,
                format="JPEG",
                quality=JPEG_QUALITY,
                subsampling=JPEG_SUBSAMPLING,
                optimize=JPEG_OPTIMIZE,
                progressive=JPEG_PROGRESSIVE,
            )
            temporary_path.replace(debug_path)
        finally:
            temporary_path.unlink(missing_ok=True)
            generated.full_size_image.close()

        _LOGGER.info("Saved full-size %s debug map to %s.", season, debug_path)

    if pixel_changed:
        if previous_pixel_hash is None:
            _LOGGER.info("The %s map was created for the first time.", season)
        else:
            _LOGGER.info("The %s map pixels changed.", season)
    else:
        _LOGGER.info("The %s map is unchanged.", season)

    return {
        "pixel_sha256": generated.pixel_sha256,
        "updated_at": updated_at,
    }, SeasonResult(season=season, pixel_changed=pixel_changed)


def run_generation(arguments: argparse.Namespace) -> tuple[SeasonResult, ...]:
    """Generate selected maps and update images/map/manifest.json."""
    if arguments.workers < MIN_WORKERS:
        message = f"--workers must be at least {MIN_WORKERS}."
        raise MapGenerationError(message)
    if arguments.timeout <= MIN_TIMEOUT_SECONDS:
        message = f"--timeout must be greater than {MIN_TIMEOUT_SECONDS}."
        raise MapGenerationError(message)
    if arguments.retries < MIN_RETRIES:
        message = f"--retries must be at least {MIN_RETRIES}."
        raise MapGenerationError(message)

    options = GeneratorOptions(
        output_directory=arguments.output_dir.resolve(),
        debug_output_directory=arguments.debug_output_dir.resolve(),
        workers=arguments.workers,
        timeout=arguments.timeout,
        retries=arguments.retries,
        full_size=arguments.full_size,
    )
    options.output_directory.mkdir(parents=True, exist_ok=True)
    manifest_path = options.output_directory / MANIFEST_FILENAME
    maps = read_manifest(manifest_path)

    selected_seasons = SEASONS if arguments.season == "both" else (arguments.season,)
    coordinates = (
        get_all_tile_coordinates()
        if options.full_size
        else get_required_tile_coordinates()
    )
    _LOGGER.info(
        "Downloading %s tiles per season; output directory: %s",
        len(coordinates),
        options.output_directory,
    )

    results: list[SeasonResult] = []
    for season in selected_seasons:
        map_entry, result = update_season(
            season,
            maps,
            coordinates,
            options,
        )
        maps[season] = map_entry
        results.append(result)

    maps["bounds"] = get_map_bounds()

    manifest_content = json.dumps(
        maps,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )
    write_text_atomically(manifest_path, f"{manifest_content}\n")

    return tuple(results)


def main(arguments: list[str] | None = None) -> int:
    """Run the map generator and return a process exit code."""
    configure_logging()
    try:
        parsed_arguments = parse_arguments(arguments)
        results = run_generation(parsed_arguments)
    except MapGenerationError, OSError, ValueError:
        _LOGGER.exception("Map generation failed.")
        return 1

    changed_seasons = tuple(result.season for result in results if result.pixel_changed)
    if changed_seasons:
        _LOGGER.info("Visible map changes detected: %s", ", ".join(changed_seasons))
    else:
        _LOGGER.info("No visible map changes detected.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
