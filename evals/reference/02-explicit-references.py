from openhandle import OpenHandle
from openhandle.models import InstagramPost, TikTokProfile


def get_resources(openhandle: OpenHandle) -> tuple[TikTokProfile, InstagramPost]:
    profile = openhandle.tiktok.profile(id="7300000000000000001").get()
    post = openhandle.instagram.post(url="https://www.instagram.com/p/Db04otPRpRH/").get()
    return profile.data, post.data
