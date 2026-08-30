from openhandle import OpenHandle
from openhandle.models import InstagramProfile


def get_profile(openhandle: OpenHandle) -> InstagramProfile:
    response = openhandle.instagram.profile("northstar_forge_test").get(freshness="24h")
    return response.data
