from openhandle import OpenHandle, Response
from openhandle.models import InstagramProfile


def get_profile_accounting(openhandle: OpenHandle) -> tuple[str | None, str | None, str]:
    response: Response[InstagramProfile] = openhandle.instagram.profile("northstar_forge_test").get()
    return response.billing.cost, response.billing.environment, response.request_id
