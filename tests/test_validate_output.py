from __future__ import annotations

import os
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "validate_output.sh"


def _fake_aws(tmp_path: Path) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    aws = bin_dir / "aws"
    aws.write_text(
        """#!/usr/bin/env python3
import os
import sys

args = sys.argv[1:]
if args[:2] == ["s3api", "list-objects-v2"]:
    query = args[args.index("--query") + 1]
    if "Contents[?Key==" in query:
        if os.environ.get("FAKE_MANIFEST_FOUND") == "1":
            print(os.environ["FAKE_MANIFEST_KEY"])
        else:
            print("None")
    else:
        print('{"parquet_files": 1, "total_prefix_bytes": 10}')
elif args[:2] == ["s3", "ls"]:
    print("2026-11-09 00:00:00 10 part-00000.parquet")
elif args[:2] == ["s3", "cp"]:
    print('{"status":"success"}')
"""
    )
    aws.chmod(0o755)
    return bin_dir


def _run_validator(tmp_path: Path, manifest_found: bool) -> subprocess.CompletedProcess[str]:
    region = "monaco"
    ymd = "20261108"
    prefix = f"curated/region={region}/{ymd[0:4]}/{ymd[4:6]}/{ymd[6:8]}/"
    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{_fake_aws(tmp_path)}:{env['PATH']}",
            "AWS_REGION": "us-east-1",
            "OUTPUT_BUCKET": "curated-bucket",
            "REGION_NAME": region,
            "YMD": ymd,
            "OUTPUT_PREFIX": "curated",
            "FAKE_MANIFEST_FOUND": "1" if manifest_found else "0",
            "FAKE_MANIFEST_KEY": f"{prefix}_manifest.json",
        }
    )
    return subprocess.run(
        ["bash", str(SCRIPT)],
        capture_output=True,
        check=False,
        env=env,
        text=True,
    )


def test_validate_output_fails_before_listing_when_manifest_is_missing(tmp_path: Path) -> None:
    result = _run_validator(tmp_path, manifest_found=False)

    assert result.returncode == 1
    assert "Refusing to validate before the partition manifest exists" in result.stderr
    assert "Objects in s3://" not in result.stdout


def test_validate_output_continues_when_manifest_exists(tmp_path: Path) -> None:
    result = _run_validator(tmp_path, manifest_found=True)

    assert result.returncode == 0
    assert "Objects in s3://curated-bucket/curated/region=monaco/2026/11/08/" in result.stdout
    assert '{"status":"success"}' in result.stdout
