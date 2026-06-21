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

logger = logging.getLogger(__name__)


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

    def write_metadata(self, directory: Path, source_url: str) -> None:
        """Write metadata file with source URL and download timestamp."""
        metadata = {
            "source_url": source_url,
            "downloaded_at": datetime.now(timezone.utc).isoformat(),
        }

        with open(directory / "metadata.json", "w") as f:
            json.dump(metadata, f, indent=2)

    def write_versions_json(self) -> None:
        """Write versions.json to track pinned versions and download date."""
        versions = {
            "attack_version": self.attack_version,
            "capec_version": self.capec_version,
            "download_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        }

        with open(self.data_dir / "versions.json", "w") as f:
            json.dump(versions, f, indent=2)

    def download_attack(self) -> None:
        """Download and save enterprise-attack dataset."""
        attack_file = self.attack_dir / "enterprise-attack.json"

        self.download_file(
            self.attack_url,
            attack_file,
        )

        self.write_metadata(self.attack_dir, self.attack_url)

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

        self.write_metadata(self.capec_dir, self.capec_url)

    def download_all(self) -> None:
        """Run download process for all datasets."""
        self.ensure_dirs()
        self.download_attack()
        self.download_capec()
        self.write_versions_json()
