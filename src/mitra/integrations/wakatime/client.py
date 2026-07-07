import os
import configparser
import httpx
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime


class WakaTimeClient:
    """Client for the WakaTime REST API."""

    def __init__(self, api_key: Optional[str] = None):
        key = api_key or os.environ.get("WAKATIME_API_KEY") or self._read_wakatime_cfg()
        if not key:
            raise ValueError(
                "WakaTime API Key not found. Please provide it as a parameter, "
                "set the WAKATIME_API_KEY environment variable, or configure it in ~/.wakatime.cfg."
            )
        self.api_key = key
        # Basic auth with key and empty password
        self.auth = (self.api_key, "")

    @staticmethod
    def _read_wakatime_cfg() -> Optional[str]:
        """Attempt to read the API key from ~/.wakatime.cfg."""
        cfg_path = Path.home() / ".wakatime.cfg"
        if cfg_path.exists():
            try:
                config = configparser.ConfigParser()
                config.read(cfg_path)
                if "settings" in config and "api_key" in config["settings"]:
                    return config["settings"]["api_key"].strip()
            except Exception:
                pass
        return None

    async def get_summaries(
        self,
        start_date: str,
        end_date: str,
        project: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Retrieves coding activity summaries for a date range.
        start_date and end_date should be in YYYY-MM-DD format.
        """
        url = "https://wakatime.com/api/v1/users/current/summaries"
        params = {"start": start_date, "end": end_date}
        if project:
            params["project"] = project

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, auth=self.auth, params=params, timeout=15.0)
                if response.status_code >= 400:
                    raise RuntimeError(f"WakaTime API error {response.status_code}: {response.text}")
                return response.json()
            except httpx.HTTPStatusError as e:
                raise RuntimeError(f"WakaTime API call failed: {e.response.status_code} - {e.response.text}")
            except Exception as e:
                raise RuntimeError(f"WakaTime connection failed: {str(e)}")

    async def get_today_projects(self) -> List[Dict[str, Any]]:
        """List all projects worked on today and their total duration."""
        today_str = datetime.now().strftime("%Y-%m-%d")
        summaries = await self.get_summaries(today_str, today_str)

        results = []
        for day in summaries.get("data", []):
            for proj in day.get("projects", []):
                results.append({
                    "name": proj.get("name"),
                    "total_seconds": proj.get("total_seconds"),
                    "digital": proj.get("digital"),
                    "text": proj.get("text"),
                })
        return results

    async def get_today_file_durations(self, project: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Fetches today's summaries and extracts coding time (duration) for each file.
        If a project name is provided, returns file breakdown for that project.
        """
        today_str = datetime.now().strftime("%Y-%m-%d")
        summaries = await self.get_summaries(today_str, today_str, project=project)

        results = []
        for day in summaries.get("data", []):
            for proj in day.get("projects", []):
                for entity in proj.get("entities", []):
                    results.append({
                        "file_path": entity.get("name"),
                        "project": proj.get("name"),
                        "total_seconds": entity.get("total_seconds"),
                        "digital": entity.get("digital"),
                        "text": entity.get("text"),
                    })
        return results

    async def get_projects_for_range(self, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """List all projects worked on during the specified time range and their total duration."""
        summaries = await self.get_summaries(start_date, end_date)

        results = []
        for day in summaries.get("data", []):
            day_date = day.get("range", {}).get("date")
            for proj in day.get("projects", []):
                results.append({
                    "date": day_date,
                    "name": proj.get("name"),
                    "total_seconds": proj.get("total_seconds"),
                    "digital": proj.get("digital"),
                    "text": proj.get("text"),
                })
        return results

    async def get_file_durations_for_range(
        self,
        start_date: str,
        end_date: str,
        project: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetches summaries for the specified time range and extracts coding time (duration) for each file.
        Can be filtered by a specific project name.
        start_date and end_date should be in YYYY-MM-DD format.
        """
        summaries = await self.get_summaries(start_date, end_date, project=project)

        results = []
        for day in summaries.get("data", []):
            day_date = day.get("range", {}).get("date")
            for proj in day.get("projects", []):
                for entity in proj.get("entities", []):
                    results.append({
                        "date": day_date,
                        "file_path": entity.get("name"),
                        "project": proj.get("name"),
                        "total_seconds": entity.get("total_seconds"),
                        "digital": entity.get("digital"),
                        "text": entity.get("text"),
                    })
        return results
