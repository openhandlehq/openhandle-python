from openhandle import OpenHandle, Response
from openhandle.models import FetchResource


def fetch_unknown_resource(openhandle: OpenHandle) -> Response[FetchResource]:
    return openhandle.fetch("https://www.instagram.com/p/Db04otPRpRH/")
