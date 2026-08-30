from openhandle import OpenHandle
from openhandle.models import TwitterProfile


def get_profile_without_retries(openhandle: OpenHandle) -> TwitterProfile:
    response = openhandle.twitter.profile("northstar_forge_test").get(timeout=5.0, max_retries=0)
    return response.data
