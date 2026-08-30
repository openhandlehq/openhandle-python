# OpenHandle Python SDK

The official Python client for the OpenHandle API.

## Installation

```bash
pip install openhandle
```

The package supports Python 3.10 and newer and ships full type annotations.

## Usage

Create a Test key in the [Openhandle dashboard](https://app.openhandle.dev),
store it as `OPENHANDLE_TEST_KEY`, and create one reusable client:

```python
import os

from openhandle import OpenHandle

openhandle = OpenHandle(api_key=os.environ["OPENHANDLE_TEST_KEY"])
profile = openhandle.instagram.profile("northstar_forge_test")

response = profile.get()
posts = profile.posts.list(freshness="24h")

print(response.data["handle"], len(posts.data))
```

The key selects the environment. `oh_test_` keys return deterministic synthetic
data with a `$0.000` actual charge; `oh_live_` keys use real public identifiers
and normal billing. Never expose an API key in client-side code.

See the [API reference](https://openhandle.dev/docs/api-reference) for a typed
SDK example for every operation.

## Resource selection

The SDK follows one predictable grammar:

```text
openhandle.<platform>.<resource>(reference).<subresource>.<operation>(options)
```

Only terminal operations such as `get`, `list`, `search`, and `fetch` perform
network requests. Selecting a resource is synchronous and reusable:

```python
post = openhandle.instagram.post("Db04otPRpRH")

response = post.get()
comments = post.comments.list()
```

A profile selector accepts a username shorthand or an explicit reference:

```python
openhandle.instagram.profile("openai")
openhandle.instagram.profile("https://www.instagram.com/openai/")
openhandle.instagram.profile(username="12356")
openhandle.instagram.profile(id="25025320")
openhandle.instagram.profile(url="https://www.instagram.com/openai/")
```

A raw string is never treated as a platform ID. `profile("12356")` selects the
username `12356`; `profile(id="12356")` selects platform ID `12356`. Numeric
reference values are rejected because platform IDs are opaque strings.

Call `openhandle.fetch(url)` when you do not know which resource a supported
social URL represents.

## Pagination

A list or search operation returns one typed page:

```python
page = openhandle.instagram.profile("northstar_forge_test").posts.list()

print(page.data, page.has_next_page, page.next_cursor)
next_page = page.next()
```

`items()` iterates lazily across pages, one request per page:

```python
for post in openhandle.instagram.profile("northstar_forge_test").posts.items():
    print(post["id"])
```

## Async client

`AsyncOpenHandle` exposes the same resource graph with `async` terminal
operations:

```python
import asyncio
import os

from openhandle import AsyncOpenHandle


async def main() -> None:
    async with AsyncOpenHandle(api_key=os.environ["OPENHANDLE_TEST_KEY"]) as openhandle:
        response = await openhandle.instagram.profile("northstar_forge_test").get()
        print(response.data["handle"])

        async for post in openhandle.instagram.profile("northstar_forge_test").posts.items():
            print(post["id"])


asyncio.run(main())
```

## Responses

Every response preserves the public envelope. `data` stays typed through the
generated models in `openhandle.models`, and metadata is available on the
response object:

```python
response = openhandle.instagram.profile("northstar_forge_test").get()

response.platform  # "instagram"
response.resource  # "profile"
response.captured_at  # datetime
response.source  # "live" or "cache"
response.request_id  # stable request identifier for logs and support
response.billing.cost  # authoritative charge as a decimal string
```

A missing metric is `None`. It is never `0`.

## Errors and retries

The SDK raises `OpenHandleError` with the documented fields. Branch on `code`,
never on `message`:

```python
from openhandle import OpenHandle, OpenHandleError

try:
    response = openhandle.instagram.profile("private_account").get()
except OpenHandleError as error:
    print(error.code, error.request_id, error.retryable)
```

Retryable failures are retried automatically with capped exponential backoff
and `Retry-After` support. Configure the client, or override per request:

```python
openhandle = OpenHandle(api_key="...", timeout=10.0, max_retries=1)
openhandle.twitter.profile("openai").get(timeout=5.0, max_retries=0)
```

Locally invalid references raise `OpenHandleReferenceError` before any request
is made. `ReferenceMismatchError` reports a social URL that belongs to a
different platform or resource than the selector.

## License

[MIT](./LICENSE)
