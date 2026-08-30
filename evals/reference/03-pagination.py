from openhandle import OpenHandle, Page
from openhandle.models import InstagramPost


def collect_post_ids(openhandle: OpenHandle) -> list[str]:
    post_ids: list[str] = []
    page: Page[InstagramPost] | None = openhandle.instagram.profile("northstar_forge_test").posts.list()
    while page is not None:
        post_ids.extend(post["id"] for post in page.data)
        page = page.next()
    return post_ids
