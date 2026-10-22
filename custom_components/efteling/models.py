"""Efteling API response models."""

from typing import NotRequired, TypedDict


class ShowTimeInfo(TypedDict):
    """Single showtime entry."""

    StartDateTime: str
    ShowDateTime: NotRequired[str | None]
    EndDateTime: NotRequired[str | None]
    Duration: NotRequired[int | None]
    Edition: NotRequired[str | None]


class AttractionInfo(TypedDict):
    """Attraction or show entry returned by the live endpoint."""

    Id: str
    Name: str
    State: str
    Type: NotRequired[str | None]
    Empire: NotRequired[str | None]
    WaitingTime: NotRequired[int | None]
    ShowTimes: NotRequired[list[ShowTimeInfo] | None]
    PastShowTimes: NotRequired[list[ShowTimeInfo] | None]


class Poi(TypedDict):
    """POI fields consumed by the integration."""

    category: str
    id: str
    name: str
    alternateid: NotRequired[str | None]
    alternatelabel: NotRequired[str | None]
    wis_info: NotRequired[AttractionInfo | None]
    detail_text: NotRequired[str | None]
    empire: NotRequired[str | None]
    image: NotRequired[str | None]
    image_detailview1: NotRequired[str | None]
    latlon: NotRequired[str | None]
    properties: NotRequired[list[str] | None]
    properties_entry_requirements: NotRequired[list[str] | None]
    properties_stimuli: NotRequired[list[str] | None]
    subtitle: NotRequired[str | None]
    targetgroups: NotRequired[list[str] | None]
    type: NotRequired[str | None]


class PoiObject(TypedDict):
    """POI wrapper object."""

    id: NotRequired[str]
    fields: Poi


class Pois(TypedDict):
    """POI list."""

    hit: list[PoiObject]


class PoiResponse(TypedDict):
    """POI (points of interest) response."""

    hits: Pois


class WaitTimesResponse(TypedDict):
    """Wait times API response."""

    Version: NotRequired[str]
    TimeStamp: NotRequired[str]
    AttractionInfo: list[AttractionInfo]


class OpeningInterval(TypedDict):
    """A single opening interval for a park date."""

    Open: NotRequired[str | None]
    Close: NotRequired[str | None]


class OpeningHours(TypedDict):
    """Park opening hours for a calendar date."""

    Date: str
    FormattedDate: NotRequired[str | None]
    OpeningHours: NotRequired[list[OpeningInterval] | None]
    Crowded: NotRequired[int | None]
    Crowdedness: NotRequired[int | None]


class Maintenance(TypedDict):
    """Attraction maintenance schedule record."""

    DateFrom: str
    DateTo: str
    Name: NotRequired[str | None]
    OpenInWeekend: NotRequired[bool | None]
    State: NotRequired[str | None]
    Type: NotRequired[str | None]
    Url: NotRequired[str | None]


class Event(TypedDict):
    """Park event schedule record."""

    DateFrom: str
    DateTo: str
    Type: str
    Name: NotRequired[str | None]
    Description: NotRequired[str | None]
    Link: NotRequired[str | None]


class ParkInfoResponse(TypedDict):
    """Park opening, maintenance, and event schedules."""

    OpeningHours: list[OpeningHours]
    Maintenance: list[Maintenance]
    Events: list[Event]


ATTRACTION_STATUS_MAP: dict[str, str] = {
    "": "closed",
    "gesloten": "closed",
    "nognietopen": "closed",
    "wachtrijgesloten": "closed",
    "open": "open",
    "inonderhoud": "under_maintenance",
    "buitenbedrijf": "out_of_order",
    "tijdelijkbuitenbedrijf": "temporarily_out_of_order",
}
