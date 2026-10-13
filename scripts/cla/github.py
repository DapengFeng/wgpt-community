"""Bounded GitHub REST transport; redirects never receive an authorization token."""

import json
import re
import urllib.error
import urllib.parse
import urllib.request


class GitHubError(RuntimeError):
    def __init__(self, status, message="GitHub API request failed"):
        self.status = status
        super().__init__(f"{message} (HTTP {status})")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, file, code, message, headers, new_url):
        return None


class GitHubClient:
    def __init__(self, token: str, *, opener=None, timeout=20):
        if not token or "\r" in token or "\n" in token:
            raise ValueError("A GitHub token is required")
        if not 0 < timeout <= 60:
            raise ValueError("Invalid GitHub request timeout")
        self._token = token
        self._opener = opener or urllib.request.build_opener(_NoRedirect())
        self._timeout = timeout

    def request(self, method, path, body=None):
        parsed = urllib.parse.urlsplit(path)
        if (
            not path.startswith("/") or path.startswith("//") or parsed.scheme
            or parsed.netloc or parsed.fragment or "\\" in path
            or re.search(r"[\x00-\x20\x7f]", path)
            or method not in {"GET", "POST", "PUT", "PATCH", "DELETE"}
        ):
            raise ValueError("Expected an absolute GitHub API path, not a URL")
        encoded = None if body is None else json.dumps(body, allow_nan=False).encode("utf-8")
        if method == "PUT" and body is None:
            # Parameterless collaborator invitations require Content-Length: 0.
            encoded = b""
        if encoded is not None and len(encoded) > 2 * 1024 * 1024:
            raise ValueError("GitHub request body exceeds limit")
        request = urllib.request.Request(
            "https://api.github.com" + path,
            data=encoded,
            method=method,
            headers={
                "Authorization": "Bearer " + self._token,
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "wgpt-community-cla",
                "Content-Type": "application/json",
            },
        )
        try:
            with self._opener.open(request, timeout=self._timeout) as response:
                if not 200 <= response.status < 300:
                    raise GitHubError(response.status)
                content = response.read(2 * 1024 * 1024 + 1)
        except urllib.error.HTTPError as error:
            raise GitHubError(error.code) from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise GitHubError(0, "GitHub transport failed") from None
        if len(content) > 2 * 1024 * 1024:
            raise ValueError("GitHub response exceeds limit")
        return json.loads(content) if content else None

    def paginate(self, path, max_pages=10):
        if not 1 <= max_pages <= 10:
            raise ValueError("Invalid GitHub pagination bound")
        parsed = urllib.parse.urlsplit(path)
        query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        if any(name in {"page", "per_page"} for name, _ in query):
            raise ValueError("Pagination parameters belong to the bounded client")
        result = []
        for page in range(1, max_pages + 1):
            suffix = urllib.parse.urlencode(query + [("per_page", 100), ("page", page)])
            batch = self.request("GET", parsed.path + "?" + suffix)
            if not isinstance(batch, list) or len(batch) > 100:
                raise ValueError("Expected a bounded GitHub result list")
            result.extend(batch)
            if len(batch) < 100:
                return result
        raise ValueError("GitHub pagination limit reached; refusing incomplete results")
