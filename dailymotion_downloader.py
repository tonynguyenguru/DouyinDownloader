import os
import re
import json
import subprocess
from typing import Optional

import requests


def extract_video_id(url: str) -> Optional[str]:
    """Extract the video ID from a Dailymotion URL."""
    patterns = [
        r"dailymotion\.com/video/([\w]+)",
        r"dai\.ly/([\w]+)"
    ]
    for pattern in patterns:
        m = re.search(pattern, url)
        if m:
            return m.group(1)
    return None


def get_direct_video_url(video_id: str) -> Optional[str]:
    """Get a direct mp4 or m3u8 URL using Dailymotion metadata API."""
    metadata_url = f"https://www.dailymotion.com/player/metadata/video/{video_id}"
    headers = {"User-Agent": "Mozilla/5.0"}
    resp = requests.get(metadata_url, headers=headers, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    qualities = data.get("qualities", {})
    for quality in ["1080", "720", "480", "380", "240", "auto"]:
        sources = qualities.get(quality, [])
        for source in sources:
            content_type = source.get("type")
            if content_type in [
                "video/mp4",
                "application/x-mpegURL",
                "application/vnd.apple.mpegurl",
            ]:
                return source.get("url")
    return None


def download_dailymotion_video(url: str, output_dir: str = "downloads") -> str:
    """Download a Dailymotion video using ffmpeg and return the output path."""
    video_id = extract_video_id(url)
    if not video_id:
        raise ValueError("Invalid Dailymotion URL")

    direct_url = get_direct_video_url(video_id)
    if not direct_url:
        raise RuntimeError("Could not find direct video URL")

    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"dailymotion_{video_id}.mp4")

    cmd = ["ffmpeg", "-y", "-i", direct_url, "-c", "copy", output_path]
    subprocess.run(cmd, check=True)
    return output_path


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python dailymotion_downloader.py <dailymotion_url>")
        sys.exit(1)

    try:
        out = download_dailymotion_video(sys.argv[1])
        print(f"Video saved to: {out}")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

