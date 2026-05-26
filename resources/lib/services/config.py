from services.torbox import TorBox
from services.trakt import Trakt
from services.real_debrid import RealDebrid
from services.types import Service


services: dict[str, Service] = {
    "real_debrid": RealDebrid,
    "trakt": Trakt,
    "torbox": TorBox
}


def get_service(name: str) -> Service:
    if name not in services:
        raise ValueError(f"Unknown service: {name}")
    return services[name]
