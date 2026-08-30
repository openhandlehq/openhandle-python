from openhandle import OpenHandle
from openhandle.models import InstagramComment


def list_replies(openhandle: OpenHandle) -> list[InstagramComment]:
    page = openhandle.instagram.post("910000000000000001").comment("18120112390529134").replies.list()
    return page.data
