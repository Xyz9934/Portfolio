import requests
import re


def _tokenize(text):
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _score_result(query, title, snippet):
    query_tokens = _tokenize(query)
    title_tokens = _tokenize(title)
    snippet_tokens = _tokenize(snippet)
    all_tokens = title_tokens | snippet_tokens

    if not query_tokens:
        return -1

    numeric_tokens = {token for token in query_tokens if token.isdigit()}
    if numeric_tokens and not numeric_tokens.issubset(all_tokens):
        return -1

    overlap = len(query_tokens & all_tokens)
    ratio = overlap / len(query_tokens)
    exact_title = 1 if query.lower().strip() == title.lower().strip() else 0
    phrase_in_title = 1 if query.lower() in title.lower() else 0

    return exact_title * 100 + phrase_in_title * 10 + ratio


def search_web(query):
    try:
        headers = {
            "User-Agent": "FRIDAY-AI"
        }

        search_url = "https://en.wikipedia.org/w/api.php"

        search_terms = [
            f'intitle:"{query}"',
            f'"{query}"',
            query,
        ]

        results = []

        for term in search_terms:
            search_params = {
                "action": "query",
                "list": "search",
                "utf8": 1,
                "srsearch": term,
                "format": "json"
            }

            r = requests.get(search_url, params=search_params, headers=headers, timeout=10)
            data = r.json()
            results = data.get("query", {}).get("search", [])

            if results:
                break

        if not results:
            return "FRIDAY could not find an answer."

        best_result = None
        best_score = -1

        for result in results[:5]:
            title = result.get("title", "")
            snippet = result.get("snippet", "")
            score = _score_result(query, title, snippet)
            if score > best_score:
                best_score = score
                best_result = result

        if not best_result or best_score < 0:
            return "FRIDAY could not find an answer."

        title = best_result["title"]

        summary_url = "https://en.wikipedia.org/api/rest_v1/page/summary/" + title.replace(" ", "%20")

        r2 = requests.get(summary_url, headers=headers, timeout=10)

        if r2.status_code != 200:
            return "FRIDAY could not fetch the summary."

        summary = r2.json()

        extract = summary.get("extract", "FRIDAY could not find an answer.")
        if _score_result(query, title, extract) < 0:
            return "FRIDAY could not find an answer."

        return extract

    except Exception as e:
        return "Search error: " + str(e)
