from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any
import urllib.error
import urllib.parse
import urllib.request


@dataclass
class VikunjaApiError(Exception):
    message: str
    status_code: int | None = None
    details: Any | None = None

    def __str__(self) -> str:
        if self.status_code is None:
            return self.message
        return f"{self.message} (status={self.status_code})"


class VikunjaClient:
    def __init__(self, base_url: str, token: str | None, timeout: float = 15.0) -> None:
        normalized = base_url.rstrip("/")
        if not normalized.endswith("/api/v1"):
            normalized = f"{normalized}/api/v1"
        self.base_url = normalized
        self.token = token
        self.timeout = timeout

    def _headers(self, auth: bool) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if auth:
            if not self.token:
                raise VikunjaApiError("Missing VIKUNJA_API_TOKEN for authenticated request")
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _request(
        self,
        method: str,
        path: str,
        *,
        auth: bool = True,
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
    ) -> Any:
        url = f"{self.base_url}{path}"
        if params:
            query = urllib.parse.urlencode(params, doseq=True)
            url = f"{url}?{query}"

        data: bytes | None = None
        headers = self._headers(auth=auth)
        if json_data is not None:
            data = json.dumps(json_data).encode("utf-8")
            headers["Content-Type"] = "application/json"

        request = urllib.request.Request(url=url, data=data, headers=headers, method=method)

        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            details: Any
            try:
                details = json.loads(body) if body else {}
            except json.JSONDecodeError:
                details = body
            message = "Vikunja API request failed"
            if isinstance(details, dict):
                message = str(details.get("message") or details.get("error") or message)
            raise VikunjaApiError(message=message, status_code=exc.code, details=details) from exc
        except urllib.error.URLError as exc:
            raise VikunjaApiError(f"HTTP request failed: {exc}") from exc

        if not raw:
            return {}

        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return {"raw": raw.decode("utf-8", errors="replace")}

    def health(self) -> dict[str, Any]:
        payload = self._request("GET", "/info", auth=False)
        return payload if isinstance(payload, dict) else {"info": payload}

    def list_projects(self, page: int = 1, per_page: int = 50) -> list[dict[str, Any]]:
        payload = self._request("GET", "/projects", params={"page": page, "per_page": per_page})
        if not isinstance(payload, list):
            raise VikunjaApiError("Unexpected response type while listing projects", details=payload)
        return payload

    def create_project(self, title: str, description: str | None = None) -> dict[str, Any]:
        body: dict[str, Any] = {"title": title}
        if description:
            body["description"] = description
        payload = self._request("PUT", "/projects", json_data=body)
        if not isinstance(payload, dict):
            raise VikunjaApiError("Unexpected response type while creating project", details=payload)
        return payload

    def list_project_views(self, project_id: int) -> list[dict[str, Any]]:
        payload = self._request("GET", f"/projects/{project_id}/views")
        if not isinstance(payload, list):
            raise VikunjaApiError("Unexpected response type while listing project views", details=payload)
        return payload

    def resolve_view_id(self, project_id: int, preferred_kind: str = "kanban") -> int:
        views = self.list_project_views(project_id)
        if not views:
            raise VikunjaApiError(f"Project {project_id} has no views")

        preferred = next((v for v in views if v.get("view_kind") == preferred_kind), None)
        if preferred and preferred.get("id") is not None:
            return int(preferred["id"])

        first = views[0].get("id")
        if first is None:
            raise VikunjaApiError(f"Could not resolve a view id for project {project_id}")
        return int(first)

    def list_buckets(self, project_id: int, view_id: int) -> list[dict[str, Any]]:
        payload = self._request("GET", f"/projects/{project_id}/views/{view_id}/buckets")
        if not isinstance(payload, list):
            raise VikunjaApiError("Unexpected response type while listing buckets", details=payload)
        return payload

    def list_tasks(
        self,
        project_id: int,
        *,
        view_id: int | None = None,
        page: int = 1,
        per_page: int = 50,
    ) -> list[dict[str, Any]]:
        selected_view_id = view_id or self.resolve_view_id(project_id)
        payload = self._request(
            "GET",
            f"/projects/{project_id}/views/{selected_view_id}/tasks",
            params={"page": page, "per_page": per_page, "expand": "buckets"},
        )
        if not isinstance(payload, list):
            raise VikunjaApiError("Unexpected response type while listing tasks", details=payload)

        # Kanban views return buckets with nested tasks. Some empty buckets may omit the
        # `tasks` field, so detect by scanning the full payload, not only first element.
        has_bucket_shape = any(isinstance(item, dict) and "tasks" in item for item in payload)
        if has_bucket_shape:
            tasks: list[dict[str, Any]] = []
            for bucket in payload:
                if not isinstance(bucket, dict):
                    continue
                bucket_id = bucket.get("id")
                for task in bucket.get("tasks", []):
                    if isinstance(task, dict):
                        task = {**task, "bucket_id": task.get("bucket_id", bucket_id)}
                        tasks.append(task)
            return tasks
        return payload

    def create_task(
        self,
        project_id: int,
        title: str,
        *,
        description: str | None = None,
        bucket_id: int | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"title": title}
        if description:
            body["description"] = description
        if bucket_id is not None:
            body["bucket_id"] = bucket_id

        payload = self._request("PUT", f"/projects/{project_id}/tasks", json_data=body)
        if not isinstance(payload, dict):
            raise VikunjaApiError("Unexpected response type while creating task", details=payload)
        return payload

    def list_task_comments(self, task_id: int, order_by: str = "asc") -> list[dict[str, Any]]:
        payload = self._request(
            "GET",
            f"/tasks/{task_id}/comments",
            params={"order_by": order_by},
        )
        if not isinstance(payload, list):
            raise VikunjaApiError("Unexpected response type while listing task comments", details=payload)
        return payload

    def add_task_comment(self, task_id: int, comment: str) -> dict[str, Any]:
        body = {"comment": comment}
        payload = self._request(
            "PUT",
            f"/tasks/{task_id}/comments",
            json_data=body,
        )
        if not isinstance(payload, dict):
            raise VikunjaApiError("Unexpected response type while creating task comment", details=payload)
        return payload

    def get_task(self, task_id: int) -> dict[str, Any]:
        payload = self._request("GET", f"/tasks/{task_id}")
        if not isinstance(payload, dict):
            raise VikunjaApiError("Unexpected response type while fetching task", details=payload)
        return payload

    def update_task(self, task_id: int, updates: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(updates, dict) or not updates:
            raise VikunjaApiError("Task update payload must be a non-empty object")
        payload = self._request("POST", f"/tasks/{task_id}", json_data=updates)
        if not isinstance(payload, dict):
            raise VikunjaApiError("Unexpected response type while updating task", details=payload)
        return payload

    def move_task(
        self,
        task_id: int,
        target_bucket_id: int,
        *,
        project_id: int | None = None,
        view_id: int | None = None,
    ) -> dict[str, Any]:
        if project_id is None:
            task = self.get_task(task_id)
            project_id = task.get("project_id")
            if project_id is None:
                raise VikunjaApiError(f"Could not resolve project_id for task {task_id}")
            project_id = int(project_id)

        resolved_view_id = view_id or self.resolve_view_id(project_id)

        body = {
            "task_id": int(task_id),
            "bucket_id": int(target_bucket_id),
            "project_view_id": int(resolved_view_id),
        }
        payload = self._request(
            "POST",
            f"/projects/{project_id}/views/{resolved_view_id}/buckets/{target_bucket_id}/tasks",
            json_data=body,
        )
        if not isinstance(payload, dict):
            raise VikunjaApiError("Unexpected response type while moving task", details=payload)
        return payload
