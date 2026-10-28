import json


MAX_QUERY_LENGTH = 500
MAX_RESULTS = 5
MAX_TITLE_LENGTH = 300
MAX_URL_LENGTH = 2048
MAX_SNIPPET_LENGTH = 1000


def _error_result(query: str, message: str) -> str:
    return json.dumps(
        {"ok": False, "query": query, "error": message},
        ensure_ascii=False,
    )


def search_web(query: str, max_results: int = 5) -> str:
    """Search the web and return bounded result metadata as JSON."""
    if not isinstance(query, str):
        return _error_result("", "Search query must be text.")

    normalized_query = query.strip()
    if not normalized_query:
        return _error_result(normalized_query, "Search query cannot be empty.")
    if len(normalized_query) > MAX_QUERY_LENGTH:
        return _error_result(
            normalized_query[:MAX_QUERY_LENGTH],
            f"Search query cannot exceed {MAX_QUERY_LENGTH} characters.",
        )

    if isinstance(max_results, bool) or not isinstance(max_results, int):
        return _error_result(
            normalized_query,
            f"max_results must be an integer between 1 and {MAX_RESULTS}.",
        )
    if not 1 <= max_results <= MAX_RESULTS:
        return _error_result(
            normalized_query,
            f"max_results must be between 1 and {MAX_RESULTS}.",
        )

    try:
        from ddgs import DDGS

        raw_results = DDGS().text(
            normalized_query,
            max_results=max_results,
        )
    except ImportError as error:
        message = str(error).strip()
        return _error_result(
            normalized_query,
            "The web-search dependency is unavailable or incomplete. "
            "Install the project requirements"
            + (f": {message}" if message else "."),
        )
    except Exception as error:
        error_name = type(error).__name__.casefold()
        error_message = str(error).strip()
        error_details = f"{error_name} {error_message.casefold()}"
        if "timeout" in error_details or isinstance(error, TimeoutError):
            message = "Web search timed out."
        elif any(
            marker in error_name
            for marker in ("connection", "connect", "network", "proxy", "transport")
        ) or any(
            marker in error_message.casefold()
            for marker in ("connection", "connect", "network", "proxy", "transport")
        ):
            message = "Web search could not connect to the search provider."
        elif "invalid impersonate" in error_message.casefold():
            message = (
                "The installed web-search client has an incompatible browser "
                "impersonation setting. Update the project's pinned search "
                "dependencies and retry."
            )
        else:
            message = f"Web search failed: {error_message or type(error).__name__}."
        return _error_result(normalized_query, message)

    if not isinstance(raw_results, list):
        return _error_result(
            normalized_query,
            "Search provider returned an unexpected response format.",
        )

    results: list[dict[str, str]] = []
    for item in raw_results[:max_results]:
        if not isinstance(item, dict):
            return _error_result(
                normalized_query,
                "Search provider returned an unexpected result format.",
            )

        title = item.get("title")
        url = item.get("href", item.get("url"))
        snippet = item.get("body", item.get("snippet"))
        if not all(isinstance(value, str) for value in (title, url, snippet)):
            return _error_result(
                normalized_query,
                "Search provider returned a result with missing or invalid fields.",
            )

        results.append({
            "title": title[:MAX_TITLE_LENGTH],
            "url": url[:MAX_URL_LENGTH],
            "snippet": snippet[:MAX_SNIPPET_LENGTH],
        })

    return json.dumps(
        {
            "ok": True,
            "query": normalized_query,
            "results": results,
            "message": "No search results found." if not results else None,
        },
        ensure_ascii=False,
    )
