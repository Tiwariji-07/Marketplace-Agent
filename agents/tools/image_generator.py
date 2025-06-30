"""Tool for generating an app icon or banner image using the OpenAI Images API (DALL·E)."""
from __future__ import annotations

import base64
import logging
from typing import Literal, Dict, Any, Optional

import aiohttp

from utils.config import settings

logger = logging.getLogger(__name__)

# Valid image kinds this tool supports
ImageKind = Literal["icon", "banner"]


class ImageGenerator:
    """Generate an icon or banner image for an app based on its name.

    This thin wrapper hits the OpenAI images API and returns a URL to the
    generated asset. If the OpenAI key is missing, a clear error is raised so
    the agent can pass it back to the user.
    """

    def __init__(self):
        if not settings.OPENAI_API_KEY:
            logger.warning("OPENAI_API_KEY is not configured – ImageGenerator will fail on calls.")
        self._session: Optional[aiohttp.ClientSession] = None

    async def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def generate(self, name: str, kind: ImageKind = "icon", size: int = 1024) -> Dict[str, Any]:
        """Generate an image and return a dict with the image URL.

        Args:
            name: The name of the app / feature.
            kind: Either "icon" (square) or "banner" (wide).
            size: Image dimension (for icons) or height (for banners).
        """
        prompt = self._build_prompt(name, kind)
        dimensions = f"{size}x{size}" if kind == "icon" else f"1024x{size}"

        headers = {
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "dall-e-3",
            "prompt": prompt,
            "n": 1,
            "size": dimensions,
        }
        session = await self._ensure_session()
        async with session.post("https://api.openai.com/v1/images/generations", json=payload, headers=headers, timeout=120) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise RuntimeError(f"OpenAI image generation failed: {resp.status} {text}")
            data = await resp.json()
            image_url = data["data"][0]["url"]
            return {"url": image_url, "kind": kind, "name": name}

    @staticmethod
    def _build_prompt(name: str, kind: ImageKind) -> str:
        if kind == "icon":
            return (
                f"Ultra-clean flat-design app icon for '{name}'. "
                "Central glyph on soft rounded square, smooth gradient background, "
                "crisp vector lines, vibrant but professional color palette, no text, no borders, "
                "transparent background outside the rounded square, designed by a top UI/UX designer."
            )
        # banner
        return (
            f"Professional wide hero banner for the application '{name}'. "
            "Elegant, modern abstract illustration, subtle depth, harmonious color gradient, "
            "minimalist style, no text, high-quality UI/UX aesthetic suitable for product landing pages."
        )

    async def __aexit__(self, *exc_info):
        if self._session and not self._session.closed:
            await self._session.close()

    async def __del__(self):
        if hasattr(self, "_session") and self._session and not self._session.closed:
            await self._session.close()
