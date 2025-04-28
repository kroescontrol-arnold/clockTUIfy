# clockify_api.py

import os
import requests
from datetime import datetime, timedelta
from debug import debug
import re 

def parse_duration(duration_str):
    if not duration_str:
        return 0
    # Example: PT8H -> 8 hours
    match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?', duration_str)
    if not match:
        return 0
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    return hours * 60 + minutes

class ClockifyAPI:
    def __init__(self):
        self.api_key = os.getenv("CLOCKIFY_API_KEY")
        if not self.api_key:
            raise ValueError("CLOCKIFY_API_KEY not set.")
        self.base_url = "https://api.clockify.me/api/v1"
        self.headers = {
            "X-Api-Key": self.api_key,
            "Content-Type": "application/json"
        }
        self.workspace_id = self.get_workspace_id()
        self.user_id = self.get_user_id()

    def get_workspace_id(self):
        resp = requests.get(f"{self.base_url}/workspaces", headers=self.headers)
        resp.raise_for_status()
        return resp.json()[0]['id']

    def get_user_id(self):
        resp = requests.get(f"{self.base_url}/user", headers=self.headers)
        resp.raise_for_status()
        return resp.json()['id']

    def get_projects(self):
        url = f"{self.base_url}/workspaces/{self.workspace_id}/projects"
        debug(f"GET {url}")
        resp = requests.get(url, headers=self.headers)
        debug("Response", resp.json())
        resp.raise_for_status()
        return resp.json()


    def get_time_entries(self, project_id, week_dates):
        start = week_dates[0].isoformat() + "T00:00:00Z"
        end = week_dates[-1].isoformat() + "T23:59:59Z"
        url = f"{self.base_url}/workspaces/{self.workspace_id}/user/{self.user_id}/time-entries"
        params = {"start": start, "end": end}
        resp = requests.get(url, headers=self.headers, params=params)
        resp.raise_for_status()
        entries = resp.json()
        debug("get_time_entries Response", resp.json())

        # Group minutes by day
        day_minutes = {}
        for entry in entries:
            if entry.get('projectId') != project_id:
                continue
            start_time = datetime.fromisoformat(entry['timeInterval']['start'].replace('Z', '+00:00'))
            duration_str = entry['timeInterval'].get('duration')
            minutes = parse_duration(duration_str)
            day = start_time.date()
            day_minutes[day] = day_minutes.get(day, 0) + minutes
        return day_minutes

    def book_time(self, project_id, date, minutes):
        if minutes <= 0:
            return
            
        # First delete any existing entries for this date and project
        # to avoid duplicate entries
        self.delete_time_entry(project_id, date)
        
        # Use 9:00 AM as a standard start time instead of midnight
        start_time = datetime.combine(date, datetime.min.time()) + timedelta(hours=9)
        end_time = start_time + timedelta(minutes=minutes)

        payload = {
            "start": start_time.isoformat() + "Z",
            "end": end_time.isoformat() + "Z",
            "billable": False,
            "description": "Booked via TUI",
            "projectId": project_id,
            "workspaceId": self.workspace_id
        }
        resp = requests.post(f"{self.base_url}/workspaces/{self.workspace_id}/time-entries", headers=self.headers, json=payload)
        resp.raise_for_status()
        return resp.json()

    def delete_time_entry(self, project_id, date):
        """Delete time entries for a specific project and date"""
        # First get the time entries for the date
        start = date.isoformat() + "T00:00:00Z"
        end = date.isoformat() + "T23:59:59Z"
        url = f"{self.base_url}/workspaces/{self.workspace_id}/user/{self.user_id}/time-entries"
        params = {"start": start, "end": end}
        
        resp = requests.get(url, headers=self.headers, params=params)
        resp.raise_for_status()
        entries = resp.json()
        
        # Delete each entry that matches the project_id
        for entry in entries:
            if entry.get('projectId') == project_id:
                entry_id = entry['id']
                delete_url = f"{self.base_url}/workspaces/{self.workspace_id}/time-entries/{entry_id}"
                delete_resp = requests.delete(delete_url, headers=self.headers)
                delete_resp.raise_for_status()
                debug(f"Deleted time entry {entry_id} for {date.isoformat()}")

