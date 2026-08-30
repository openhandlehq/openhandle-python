from openhandle import OpenHandle


def create_client(api_key: str) -> OpenHandle:
    return OpenHandle(api_key=api_key)
