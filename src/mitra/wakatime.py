import os
import configparser
import httpx
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

def get_wakatime_api_key() -> Optional[str]:
    """Retrieves the WakaTime API key from context, environment variables, config file, or ~/.wakatime.cfg."""
    # Priority 1: Request context (for multi-user remote server via HTTP headers)
    try:
        from mitra.config import request_wakatime_api_key
        api_key = request_wakatime_api_key.get()
        if api_key:
            return api_key
    except Exception:
        pass

    # Priority 2: Environment variable
    api_key = os.environ.get("WAKATIME_API_KEY")
    if api_key:
        return api_key
        
    # Priority 3: Config file (mitra config)
    try:
        from mitra.config import load_config
        config = load_config()
        if config.get("WAKATIME_API_KEY"):
            return config.get("WAKATIME_API_KEY")
    except Exception:
        pass
        
    # Priority 4: ~/.wakatime.cfg file
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


class WakaTimeClient:
    def __init__(self, api_key: Optional[str] = None):
        key = api_key or get_wakatime_api_key()
        if not key:
            raise ValueError(
                "WakaTime API Key not found. Please set the WAKATIME_API_KEY environment variable "
                "or configure it in ~/.wakatime.cfg."
            )
        self.api_key = key
        # Basic auth with key and empty password
        self.auth = (self.api_key, "")

    async def get_summaries(
        self,
        start_date: str,
        end_date: str,
        project: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Retrieves coding activity summaries for a date range.
        start_date and end_date should be in YYYY-MM-DD format.
        """
        url = "https://wakatime.com/api/v1/users/current/summaries"
        params = {
            "start": start_date,
            "end": end_date
        }
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
        data_list = summaries.get("data", [])
        for day in data_list:
            projects_list = day.get("projects", [])
            for proj in projects_list:
                results.append({
                    "name": proj.get("name"),
                    "total_seconds": proj.get("total_seconds"),
                    "digital": proj.get("digital"),
                    "text": proj.get("text")
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
        data_list = summaries.get("data", [])
        for day in data_list:
            projects_list = day.get("projects", [])
            for proj in projects_list:
                # If a specific project was queried, the response will contain entities (files)
                entities = proj.get("entities", [])
                for entity in entities:
                    results.append({
                        "file_path": entity.get("name"),
                        "project": proj.get("name"),
                        "total_seconds": entity.get("total_seconds"),
                        "digital": entity.get("digital"),
                        "text": entity.get("text")
                    })
        return results

    async def get_projects_for_range(self, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """List all projects worked on during the specified time range and their total duration."""
        summaries = await self.get_summaries(start_date, end_date)
        
        results = []
        data_list = summaries.get("data", [])
        for day in data_list:
            day_date = day.get("range", {}).get("date")
            projects_list = day.get("projects", [])
            for proj in projects_list:
                results.append({
                    "date": day_date,
                    "name": proj.get("name"),
                    "total_seconds": proj.get("total_seconds"),
                    "digital": proj.get("digital"),
                    "text": proj.get("text")
                })
        return results

    async def get_file_durations_for_range(
        self,
        start_date: str,
        end_date: str,
        project: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetches summaries for the specified time range and extracts coding time (duration) for each file.
        If a project name is provided, returns file breakdown for that project.
        """
        summaries = await self.get_summaries(start_date, end_date, project=project)
        
        results = []
        data_list = summaries.get("data", [])
        for day in data_list:
            day_date = day.get("range", {}).get("date")
            projects_list = day.get("projects", [])
            for proj in projects_list:
                entities = proj.get("entities", [])
                for entity in entities:
                    results.append({
                        "date": day_date,
                        "file_path": entity.get("name"),
                        "project": proj.get("name"),
                        "total_seconds": entity.get("total_seconds"),
                        "digital": entity.get("digital"),
                        "text": entity.get("text")
                    })
        return results

