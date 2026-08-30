from openhandle import OpenHandle
from openhandle.models import TikTokPost


def search_posts(openhandle: OpenHandle) -> list[TikTokPost]:
    page = openhandle.tiktok.search.posts.list(q="synthetic", freshness="24h")
    return page.data
