"""Efteling API response models."""

from dataclasses import dataclass
from typing import NotRequired, TypedDict


@dataclass
class PoiResponse(TypedDict):
    """POI (points of interest) response."""

    hits: Pois


@dataclass
class Pois(TypedDict):
    """POI list."""

    hit: list[PoiObject]


@dataclass
class PoiObject(TypedDict):
    """POI wrapper object."""

    id: str
    fields: Poi


@dataclass
class Poi(TypedDict):
    """POI."""

    area_id: str
    can_order: bool
    category: str
    detail_text: str
    empire: str
    has_assortment: bool
    hide_in_app: bool
    id: str
    image: str
    image_detailview1: str
    image_detailview2: str
    image_detailview3: str
    language: str
    latlon: str
    minimum_length: str
    name: str
    properties: list[str]
    properties_entry_requirements: list[str]
    properties_practical_information: list[str]
    properties_stimuli: list[str]
    search_keywords: str
    showduration: str
    subtitle: str
    text: str
    type: str
    targetgroups: list[str]
    accessibility_description: str
    accessibility_group_size: str
    accessibility_video_url: str
    alternateid: NotRequired[str]
    alternatelabel: str
    alternatetype: str
    digipass_partner_id: str
    wis_info: AttractionInfo


@dataclass
class WaitTimesResponse(TypedDict):
    """Wait times API response."""

    Version: str
    TimeStamp: str
    AttractionInfo: list[AttractionInfo]


@dataclass
class AttractionInfo(TypedDict):
    """Attraction info."""

    Id: str
    Name: str
    Type: str
    Empire: str
    State: str
    WaitingTime: NotRequired[int]
    ShowTimes: NotRequired[list[ShowTimeInfo]]
    PastShowTimes: NotRequired[list[ShowTimeInfo]]


class ShowTimeInfo(TypedDict):
    """Single showtime entry."""

    ShowDateTime: str
    StartDateTime: str
    EndDateTime: str
    Duration: int
    Edition: str


ATTRACTION_STATE_MAP: dict[str, str] = {
    "": "Gesloten",
    "gesloten": "Gesloten",
    "nognietopen": "Gesloten",
    "open": "Open",
    "inonderhoud": "In onderhoud",
    "buitenbedrijf": "Buiten bedrijf",
    "tijdelijkbuitenbedrijf": "Tijdelijk buiten bedrijf",
}
