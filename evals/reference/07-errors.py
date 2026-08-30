from openhandle import OpenHandle, OpenHandleError


def describe_failure(openhandle: OpenHandle) -> tuple[str, str | None, bool] | None:
    try:
        openhandle.instagram.profile("wanderline_private_test").get()
    except OpenHandleError as error:
        return error.code, error.request_id, error.retryable
    return None
