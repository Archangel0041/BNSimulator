"""Icon manager for loading and caching game icons.

This module handles loading PNG icons for units, abilities, status effects, and stats.
Icons are cached to avoid repeated file I/O operations.
"""
from __future__ import annotations
from pathlib import Path
from typing import Optional, Dict
import logging

try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    logging.warning("PIL/Pillow not available. Icon display will be disabled.")


class IconManager:
    """Manages loading and caching of game icons."""

    def __init__(self, icons_dir: str | Path):
        """
        Initialize icon manager.

        Args:
            icons_dir: Path to the icons directory (data/Assets/Art/icons)
        """
        self.icons_dir = Path(icons_dir)
        self.abilities_dir = self.icons_dir / "abilities"
        self.units_dir = self.icons_dir / "units"
        self.status_dir = self.icons_dir / "status_effects"
        self.stats_dir = self.icons_dir / "unit_stats"

        # Cache for loaded icons
        self._icon_cache: Dict[str, any] = {}
        self._tk_cache: Dict[str, any] = {}

        # Check if PIL is available
        self.pil_available = PIL_AVAILABLE

    def _load_image(self, path: Path, size: tuple[int, int] = None) -> Optional[Image.Image]:
        """
        Load an image from path.

        Args:
            path: Path to image file
            size: Optional (width, height) to resize to

        Returns:
            PIL Image or None if not found/error
        """
        if not self.pil_available:
            return None

        if not path.exists():
            return None

        try:
            img = Image.open(path)
            if size:
                img = img.resize(size, Image.Resampling.LANCZOS)
            return img
        except Exception as e:
            logging.warning(f"Failed to load icon from {path}: {e}")
            return None

    def _get_cached_or_load(self, cache_key: str, path: Path, size: tuple[int, int] = None) -> Optional[Image.Image]:
        """Get image from cache or load it."""
        if cache_key in self._icon_cache:
            return self._icon_cache[cache_key]

        img = self._load_image(path, size)
        if img:
            self._icon_cache[cache_key] = img
        return img

    def get_ability_icon(self, ability_name: str, size: tuple[int, int] = None) -> Optional[Image.Image]:
        """
        Get ability icon by name.

        Args:
            ability_name: Name like "abil_air_agent_orange" (without _name suffix)
            size: Optional (width, height) to resize to

        Returns:
            PIL Image or None if not found
        """
        cache_key = f"ability:{ability_name}:{size}"

        # Try with _icon suffix
        icon_path = self.abilities_dir / f"{ability_name}_icon.png"
        img = self._get_cached_or_load(cache_key, icon_path, size)
        if img:
            return img

        # Try without _icon suffix in case name already has it
        icon_path = self.abilities_dir / f"{ability_name}.png"
        return self._get_cached_or_load(cache_key, icon_path, size)

    def get_unit_icon(self, unit_name: str, facing: str = "back", size: tuple[int, int] = None) -> Optional[Image.Image]:
        """
        Get unit icon by name.

        Args:
            unit_name: Name like "veh_ancient_robot_player" (without _name suffix)
            facing: "back" or "front"
            size: Optional (width, height) to resize to

        Returns:
            PIL Image or None if not found
        """
        cache_key = f"unit:{unit_name}:{facing}:{size}"

        # Try with army_view_ prefix
        icon_path = self.units_dir / facing / f"army_view_{unit_name}.png"
        img = self._get_cached_or_load(cache_key, icon_path, size)
        if img:
            return img

        # Try without prefix
        icon_path = self.units_dir / facing / f"{unit_name}.png"
        return self._get_cached_or_load(cache_key, icon_path, size)

    def get_status_icon(self, status_name: str, size: tuple[int, int] = None) -> Optional[Image.Image]:
        """
        Get status effect icon by name.

        Args:
            status_name: Name like "stun", "poison", etc.
            size: Optional (width, height) to resize to

        Returns:
            PIL Image or None if not found
        """
        cache_key = f"status:{status_name}:{size}"

        # Try with bn_icon_ prefix
        icon_path = self.status_dir / f"bn_icon_{status_name}.png"
        img = self._get_cached_or_load(cache_key, icon_path, size)
        if img:
            return img

        # Try with suppressor_ prefix
        icon_path = self.status_dir / f"suppressor_{status_name}_icon.png"
        img = self._get_cached_or_load(cache_key, icon_path, size)
        if img:
            return img

        # Try exact name with _icon suffix
        icon_path = self.status_dir / f"{status_name}_icon.png"
        return self._get_cached_or_load(cache_key, icon_path, size)

    def get_stat_icon(self, stat_name: str, size: tuple[int, int] = None) -> Optional[Image.Image]:
        """
        Get unit stat icon by name.

        Args:
            stat_name: Name like "hp", "defense", "accuracy", etc.
            size: Optional (width, height) to resize to

        Returns:
            PIL Image or None if not found
        """
        cache_key = f"stat:{stat_name}:{size}"

        icon_path = self.stats_dir / f"unit_stat_{stat_name}_icon.png"
        return self._get_cached_or_load(cache_key, icon_path, size)

    def get_tk_icon(self, cache_key: str, pil_image: Image.Image) -> Optional[any]:
        """
        Convert PIL image to Tkinter PhotoImage and cache it.

        Args:
            cache_key: Unique key for caching
            pil_image: PIL Image to convert

        Returns:
            Tkinter PhotoImage or None
        """
        if not self.pil_available or not pil_image:
            return None

        if cache_key in self._tk_cache:
            return self._tk_cache[cache_key]

        try:
            tk_image = ImageTk.PhotoImage(pil_image)
            self._tk_cache[cache_key] = tk_image
            return tk_image
        except Exception as e:
            logging.warning(f"Failed to convert to Tkinter image: {e}")
            return None

    def get_ability_tk_icon(self, ability_name: str, size: tuple[int, int] = (32, 32)) -> Optional[any]:
        """Get ability icon as Tkinter PhotoImage."""
        img = self.get_ability_icon(ability_name, size)
        if img:
            return self.get_tk_icon(f"tk_ability:{ability_name}:{size}", img)
        return None

    def get_unit_tk_icon(self, unit_name: str, facing: str = "back", size: tuple[int, int] = (48, 48)) -> Optional[any]:
        """Get unit icon as Tkinter PhotoImage."""
        img = self.get_unit_icon(unit_name, facing, size)
        if img:
            return self.get_tk_icon(f"tk_unit:{unit_name}:{facing}:{size}", img)
        return None

    def get_status_tk_icon(self, status_name: str, size: tuple[int, int] = (24, 24)) -> Optional[any]:
        """Get status effect icon as Tkinter PhotoImage."""
        img = self.get_status_icon(status_name, size)
        if img:
            return self.get_tk_icon(f"tk_status:{status_name}:{size}", img)
        return None

    def clear_cache(self):
        """Clear all cached icons."""
        self._icon_cache.clear()
        self._tk_cache.clear()
