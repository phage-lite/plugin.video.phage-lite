from enum import Enum


class ItemType(Enum):
    MOVIE = "movie"
    SHOW = "show"

class Scrapers(Enum):
    TORRENTIO = "torrentio"
    COCO = "cocoscrapers"

