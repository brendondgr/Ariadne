#!/usr/bin/env python3

from __future__ import annotations

import json
import shutil
import zipfile
import logging
from datetime import datetime, timezone
from pathlib import Path

import requests

logger = logging.getLogger(__name__)


class DatasetDownloader:
    """Class to manage downloading MITRE ATT&CK and CAPEC datasets."""

    ATTACK_URL = (
        "https://raw.githubusercontent.com/"
        "mitre-attack/attack-stix-data/master/"
        "enterprise-attack/enterprise-attack.json"
    )

    CAPEC_URL = (
        "https://capec.mitre.org/data/xml/"
        "capec_latest.xml"
    )

    def __init__(self, data_dir: str | Path = "data", force: bool = False) -> None:
        self.data_dir = Path(data_dir)
        self.raw_dir = self.data_dir / "raw"
        self.attack_dir = self.raw_dir / "attack"
        self.capec_dir = self.raw_dir / "capec"
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

    def download_attack(self) -> None:
        """Download and save enterprise-attack dataset."""
        attack_file = self.attack_dir / "enterprise-attack.json"

        self.download_file(
            self.ATTACK_URL,
            attack_file,
        )

        self.write_metadata(self.attack_dir, self.ATTACK_URL)

    def download_capec(self) -> None:
        """Download, save, and extract CAPEC dataset."""
        if self.CAPEC_URL.endswith(".zip"):
            zip_path = self.capec_dir / "capec_latest.xml.zip"
            self.download_file(
                self.CAPEC_URL,
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
                self.CAPEC_URL,
                xml_path,
            )

        self.write_metadata(self.capec_dir, self.CAPEC_URL)

    def download_all(self) -> None:
        """Run download process for all datasets."""
        self.ensure_dirs()
        self.download_attack()
        self.download_capec()
