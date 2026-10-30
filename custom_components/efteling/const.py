"""Constants for Efteling."""

from logging import Logger, getLogger
from zoneinfo import ZoneInfo

LOGGER: Logger = getLogger(__package__)

DOMAIN = "efteling"
NAME = "Efteling"
ATTRACTIONS = "attractions"
SHOWS = "shows"
PARK = "park"

CONF_LANGUAGE = "language"
PARK_TIME_ZONE = ZoneInfo("Europe/Amsterdam")

WAIT_TIMES_URL = "https://api.efteling.com/app/wis"
POINTS_OF_INTEREST_URL = "https://api.efteling.com/app/poi"
PARK_INFO_URL = "https://www.efteling.com/service/cached/getpoiinfo"

APP_HEADERS = {
    "host": "api.efteling.com",
    "x-app-id": "nl.efteling.app.Efteling",
    "accept": "*/*",
    "x-app-name": "Efteling",
    "x-app-platform": "iOS",
    "accept-encoding": "gzip, deflate, br",
    "x-app-timezone": PARK_TIME_ZONE.key,
    "user-agent": "Efteling/22805 CFNetwork/3860.400.51 Darwin/25.3.0",
}

CUSTOM_ATTRACTION_ICONS: dict[str, str] = {
    "archipel": "mdi:waves",
    "baron1898": "mdi:mine",
    "baron1898singlerider": "mdi:mine",
    "carnavalfestival": "mdi:earth",
    "carrouselsantonpieckplein": "mdi:horse",
    "dansemacabre": "mdi:skull",
    "dansemacabresinglerider": "mdi:skull",
    "devliegendehollander": "mdi:sail-boat",
    "devliegendehollandersinglerider": "mdi:sail-boat",
    "diorama": "mdi:train-car-caboose",
    "doudetuffer": "mdi:golf-cart",
    "droomvlucht": "mdi:sleep",
    "eftelingmuseum": "mdi:image-frame",
    "fabula": "mdi:paw",
    "fatamorgana": "mdi:mosque",
    "gamegallery": "mdi:bullseye-arrow",
    "gondoletta": "mdi:duck",
    "halvemaen": "mdi:sail-boat-sink",
    "hooghmoed": "mdi:mine",
    "jorisendedraak": "mdi:sword",
    "jorisendedraaksinglerider": "mdi:sword",
    "kinderspoor": "mdi:train",
    "kindervreugd": "mdi:seesaw",
    "kleuterhof": "mdi:seesaw",
    "maxmoritz": "mdi:pretzel",
    "maxmoritzsinglerider": "mdi:pretzel",
    "pagode": "mdi:temple-buddhist",
    "pirana": "mdi:waterfall",
    "python": "mdi:snake",
    "pythonsinglerider": "mdi:snake",
    "sirocco": "mdi:sync",
    "speelbosnest": "mdi:slide",
    "sprookjesbos": "mdi:forest",
    "stoomcarrousel": "mdi:horse",
    "stoomtreinm": "mdi:railroad-light",
    "stoomtreinr": "mdi:railroad-light",
    "symbolica": "mdi:castle",
    "symbolicasinglerider": "mdi:castle",
    "vermolenmolen": "mdi:horse",
    "villavolta": "mdi:home-variant",
    "vogelrok": "mdi:bird",
    "volkvanlaaf": "mdi:home-group",
    "volkvanlaafmonorail": "mdi:snail",
}

CUSTOM_SHOW_ICONS: dict[str, str] = {
    "anderbergmusikverein": "mdi:trumpet",
    "aquanura": "mdi:fountain",
    "caro": "mdi:horse-human",
    "dancingwiththedolls": "mdi:dance-ballroom",
    "dehuyveraars": "mdi:human-queue",
    "djezel": "mdi:donkey",
    "djinnfatamorganaplein": "mdi:mosque",
    "droomvluchtelfjes": "mdi:human-female-female",
    "drcharlatanscabaretmacabre": "mdi:bottle-tonic-plus",
    "eenavondmetwolf": "mdi:dog-side",
    "jokieenjet": "mdi:bird",
    "magicaluna": "mdi:bed",
    "maxenmoritz": "mdi:pretzel",
    "ontmoeteftelingbewoners": "mdi:human-greeting",
    "pardoesdetovernar": "mdi:magic-staff",
    "prinsespardijn": "mdi:human-female-dance",
    "sprookjesboomerwaseens": "mdi:tree",
    "sprookjessprokkelaar": "mdi:basket-fill",
    "thebigbadwolfband": "mdi:microphone-variant",
    "therednoseboogieboys": "mdi:microphone-variant",
}

USE_ATTRACTION_INFO_NAME: frozenset[str] = frozenset(
    {
        "stoomtreinm",
        "stoomtreinr",
    }
)

AVERAGE_WAIT_TIME_EXCLUDED_ATTRACTIONS: frozenset[str] = frozenset(
    {
        "stoomtreinm",
        "stoomtreinr",
    }
)
