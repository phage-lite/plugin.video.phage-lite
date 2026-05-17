from services.trakt import Trakt
from services.real_debrid import RealDebrid
from services.types import Service


services: dict[str, Service] = {
    "real_debrid": RealDebrid,
    "trakt": Trakt,
    # "tmdb": {
    #     "base_url": "https://api.themoviedb.org/3",
    #     "auth_style": "bearer",
    #     "token_key": "tmdb.token",
    #     "headers": lambda: {
    #         "accept": "application/json",
    #         "content-type": "application/json",
    #     },
    # },
    # "tmdb_v4": {
    #     "base_url": "https://api.themoviedb.org/4",
    #     "auth_style": "bearer",
    #     "token_key": "tmdb.token",
    #     "headers": lambda: {
    #         "accept": "application/json",
    #         "content-type": "application/json",
    #     },
    # },
}

def get_service(name: str) -> Service:
    if name not in services:
        raise ValueError(f"Unknown service: {name}")
    return services[name]
