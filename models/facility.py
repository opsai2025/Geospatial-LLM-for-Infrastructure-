"""Normalized facility record."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

OSM_ELEMENT_TYPES = ("node", "way", "relation")


@dataclass
class Facility:
    """One OSM element normalized into a display category.

    Missing values are kept as ``None``; nothing is inferred or invented.
    ``raw_tags`` holds the original OSM tags unchanged.
    """

    osm_type: str
    osm_id: int
    name: str | None
    category: str
    category_label: str
    latitude: float
    longitude: float
    address: str | None = None
    operator: str | None = None
    phone: str | None = None
    website: str | None = None
    raw_tags: dict[str, str] = field(default_factory=dict)
    location_precision: str = "osm_node"
    source: str = "OpenStreetMap"
    retrieved_at: str = ""
    quality_flags: list[str] = field(default_factory=list)

    @property
    def source_id(self) -> str:
        """Stable source identifier, e.g. ``way/123456``."""
        return f"{self.osm_type}/{self.osm_id}"

    @property
    def osm_url(self) -> str:
        return f"https://www.openstreetmap.org/{self.osm_type}/{self.osm_id}"

    @property
    def has_name(self) -> bool:
        return bool(self.name)

    def add_flag(self, flag: str) -> None:
        if flag not in self.quality_flags:
            self.quality_flags.append(flag)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["source_id"] = self.source_id
        data["osm_url"] = self.osm_url
        return data
