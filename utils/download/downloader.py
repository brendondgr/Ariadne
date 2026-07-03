#!/usr/bin/env python3

from __future__ import annotations

import json
import shutil
import zipfile
import logging
from datetime import datetime, timezone
from pathlib import Path

import requests

from utils.config import env_str
from utils.kg_builder.io import file_sha256

logger = logging.getLogger(__name__)


def checksum_record(path: Path) -> dict[str, object]:
    """Return the sha256 + size pin for a raw source file on disk."""
    return {"sha256": file_sha256(path), "size_bytes": path.stat().st_size}


def _attack_url(version: str) -> str:
    """Build the enterprise-attack STIX bundle URL for a given version."""
    return (
        "https://raw.githubusercontent.com/"
        "mitre-attack/attack-stix-data/master/"
        f"enterprise-attack/enterprise-attack-{version}.json"
    )


def _capec_url(version: str) -> str:
    """Build the CAPEC XML catalog URL for a given version."""
    return f"https://capec.mitre.org/data/xml/capec_v{version}.xml"


class DatasetDownloader:
    """Class to manage downloading MITRE ATT&CK and CAPEC datasets."""

    # Class-level defaults. Effective values are resolved per-instance from the
    # central .env (ATTACK_VERSION / CAPEC_VERSION / ARIADNE_DATA_DIR) in
    # __init__, falling back to these constants when the env vars are unset.
    ATTACK_VERSION = "19.0"
    CAPEC_VERSION = "3.9"

    ATTACK_URL = _attack_url(ATTACK_VERSION)
    CAPEC_URL = _capec_url(CAPEC_VERSION)

    def __init__(self, data_dir: str | Path | None = None, force: bool = False) -> None:
        self.attack_version = env_str("ATTACK_VERSION", self.ATTACK_VERSION)
        self.capec_version = env_str("CAPEC_VERSION", self.CAPEC_VERSION)
        self.attack_url = _attack_url(self.attack_version)
        self.capec_url = _capec_url(self.capec_version)

        if data_dir is None:
            data_dir = env_str("ARIADNE_DATA_DIR", "data")
        self.data_dir = Path(data_dir)
        self.raw_dir = self.data_dir / "raw"
        self.attack_dir = self.raw_dir / "attack" / f"v{self.attack_version}"
        self.capec_dir = self.raw_dir / "capec" / f"v{self.capec_version}"
        self.force = force
        # Populated as each source is written/pinned: dataset -> checksum record.
        self._checksums: dict[str, dict[str, object]] = {}

    def ensure_dirs(self) -> None:
        """Ensure that output directories exist."""
        self.attack_dir.mkdir(parents=True, exist_ok=True)
        self.capec_dir.mkdir(parents=True, exist_ok=True)

    def download_file(self, url: str, destination: Path) -> None:
        """Download a file from url to destination."""
        if destination.exists() and not self.force:
            logger.info(f"[skip] {destination}")
            return

        logger.info(f"[download] {url}")

        with requests.get(url, stream=True, timeout=120) as response:
            response.raise_for_status()
            # GitHub raw serves gzip-encoded bodies; decode_content decompresses on read.
            response.raw.decode_content = True

            with open(destination, "wb") as f:
                shutil.copyfileobj(response.raw, f)

        logger.info(f"[saved] {destination}")

    def write_metadata(
        self,
        directory: Path,
        source_url: str,
        data_file: Path,
        dataset: str,
        *,
        downloaded_at: str | None = None,
    ) -> None:
        """Write metadata with source URL, timestamp, and a sha256 snapshot pin."""
        checksum = checksum_record(data_file)
        self._checksums[dataset] = checksum
        metadata = {
            "source_url": source_url,
            "downloaded_at": downloaded_at or datetime.now(timezone.utc).isoformat(),
            "sha256": checksum["sha256"],
            "size_bytes": checksum["size_bytes"],
        }

        with open(directory / "metadata.json", "w") as f:
            json.dump(metadata, f, indent=2)

    def write_versions_json(self, *, preserve_download_date: bool = False) -> None:
        """Write versions.json to pin versions, download date, and source checksums."""
        download_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        versions_path = self.data_dir / "versions.json"
        if preserve_download_date and versions_path.exists():
            with open(versions_path, encoding="utf-8") as f:
                existing = json.load(f)
            download_date = existing.get("download_date", download_date)

        versions = {
            "attack_version": self.attack_version,
            "capec_version": self.capec_version,
            "download_date": download_date,
            "checksums": {
                "attack": self._checksums.get("attack", {}),
                "capec": self._checksums.get("capec", {}),
            },
        }

        with open(versions_path, "w") as f:
            json.dump(versions, f, indent=2)
            f.write("\n")

    def pin_snapshot(self) -> dict[str, dict[str, object]]:
        """Backfill checksums for raw files already on disk without re-downloading.

        Records the sha256/size pin into each source's metadata.json and into
        versions.json, preserving the original download date. Use this to pin an
        existing snapshot that was fetched before checksums were recorded.
        """
        attack_file = self.attack_dir / "enterprise-attack.json"
        capec_file = self.capec_dir / "capec_latest.xml"
        for dataset, directory, url, data_file in (
            ("attack", self.attack_dir, self.attack_url, attack_file),
            ("capec", self.capec_dir, self.capec_url, capec_file),
        ):
            if not data_file.exists():
                raise FileNotFoundError(
                    f"Cannot pin {dataset}: raw file missing at {data_file}. "
                    "Run `uv run main.py --download` first."
                )
            source_url = url
            downloaded_at: str | None = None
            metadata_path = directory / "metadata.json"
            if metadata_path.exists():
                with open(metadata_path, encoding="utf-8") as f:
                    existing_meta = json.load(f)
                source_url = existing_meta.get("source_url", url)
                downloaded_at = existing_meta.get("downloaded_at")
            self.write_metadata(
                directory, source_url, data_file, dataset, downloaded_at=downloaded_at
            )
        self.write_versions_json(preserve_download_date=True)
        return dict(self._checksums)

    def download_attack(self) -> None:
        """Download and save enterprise-attack dataset."""
        attack_file = self.attack_dir / "enterprise-attack.json"

        self.download_file(
            self.attack_url,
            attack_file,
        )

        self.write_metadata(self.attack_dir, self.attack_url, attack_file, "attack")

    def download_capec(self) -> None:
        """Download, save, and extract CAPEC dataset."""
        if self.capec_url.endswith(".zip"):
            zip_path = self.capec_dir / "capec_latest.xml.zip"
            self.download_file(
                self.capec_url,
                zip_path,
            )

            xml_path = self.capec_dir / "capec_latest.xml"
            if self.force or not xml_path.exists():
                logger.info("[extract] CAPEC XML")
                with zipfile.ZipFile(zip_path, "r") as zf:
                    zf.extractall(self.capec_dir)
        else:
            xml_path = self.capec_dir / "capec_latest.xml"
            self.download_file(
                self.capec_url,
                xml_path,
            )

        self.write_metadata(self.capec_dir, self.capec_url, xml_path, "capec")

    def download_all(self) -> None:
        """Run download process for all datasets."""
        self.ensure_dirs()
        self.download_attack()
        self.download_capec()
        self.write_versions_json()
