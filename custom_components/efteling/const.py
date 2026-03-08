"""Constants for Efteling."""

from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

DOMAIN = "efteling"
NAME = "Efteling"

WAIT_TIMES_URL = "https://api.efteling.com/app/wis"

CUSTOM_ICONS: dict[str, str] = {
    "archipel": "mdi:waves",
    "badhuys": "mdi:pool",
    "baron1898": "mdi:mine",
    "baron1898singlerider": "mdi:mine",
    "carnavalfestival": "mdi:earth",
    "carrouselsantonpieckplein": "mdi:horse",
    "dansemacabre": "mdi:skull",
    "dansemacabresinglerider": "mdi:skull",
    "devliegendehollander": "mdi:sail-boat",
    "devliegendehollandersinglerider": "mdi:sail-boat",
    "dezeszwanenrondvaart": "mdi:duck",
    "diorama": "mdi:train-car-caboose",
    "doudetuffer": "mdi:golf-cart",
    "droomvlucht": "mdi:sleep",
    "eftelingmuseum": "mdi:image-frame",
    "fabula": "mdi:paw",
    "fatamorgana": "mdi:mosque",
    "gondoletta": "mdi:duck",
    "halvemaen": "mdi:sail-boat-sink",
    "jorisendedraak": "mdi:sword",
    "jorisendedraaksinglerider": "mdi:sword",
    "kinderspoor": "mdi:train",
    "kindervreugd": "mdi:seesaw",
    "kleuterhof": "mdi:seesaw",
    "maxmoritz": "mdi:pretzel",
    "maxmoritzsinglerider": "mdi:pretzel",
    "pagode": "mdi:temple-buddhist",
    "pirana": "mdi:waterfall",
    "poolenspa": "mdi:pool",
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
    "virtueledroomvlucht": "mdi:sleep",
    "vogelrok": "mdi:bird",
    "volkvanlaaf": "mdi:home-group",
    "volkvanlaafmonorail": "mdi:snail",
}
