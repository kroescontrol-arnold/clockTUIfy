# app.py

import os
import asyncio
import uuid
from datetime import datetime, timedelta
from dotenv import load_dotenv
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Input, Static, Select
from textual.containers import Horizontal
from textual.binding import Binding
from clockify_api import ClockifyAPI
from week_utils import get_week_dates, is_future_date
from debug import debug

load_dotenv()

class ClockifyTUI(App):
    CSS_PATH = "app.css"
    TITLE = "Clockify TUI"
    
    # Define bindings for the application
    BINDINGS = [
        Binding("ctrl+m", "set_default", "Set Default"),
        Binding("ctrl+s", "submit", "Submit"),
        Binding("escape", "handle_escape", "Back/Exit"),
        Binding("ctrl+left", "prev_week", "Week", priority=True),
        Binding("ctrl+right", "next_week", "Week", priority=True),
    ]
    
    def __init__(self):
        super().__init__()
        self.api = ClockifyAPI()
        self.projects = self.api.get_projects()
        # Filter out archived projects
        self.projects = [p for p in self.projects if not p.get('archived', False)]
        self.selected_project_id = None
        self.selected_project_name = None
        self.week_offset = 0
        self.inputs = []
        self.prefilled_hours = {}
        
        # Try to load default project from environment variable
        default_project_id = os.getenv("DEFAULT_PROJECT_ID")
        if default_project_id:
            self.selected_project_id = default_project_id
            # Set the project name
            for project in self.projects:
                if project['id'] == self.selected_project_id:
                    self.selected_project_name = project['clientName']
                    break
                    
        self._refresh_widget_ids()

    def _refresh_widget_ids(self):
        """Generate new unique IDs for all widgets"""
        self._select_id = f"project_select_{uuid.uuid4().hex[:8]}"
        self._week_label_id = f"week_label_{uuid.uuid4().hex[:8]}"
        self._horizontal_id = f"days_container_{uuid.uuid4().hex[:8]}"
    
    async def refresh_ui_with_data(self):
        """Helper function to refresh the UI with current data and focus on the first input"""
        week = get_week_dates(self.week_offset)
        
        # Only fetch data if we have a selected project
        if self.selected_project_id:
            self.prefilled_hours = self.api.get_time_entries(self.selected_project_id, week)
            
        self._refresh_widget_ids()
        await self.reset_ui()
        
        # Focus on the first input field if available
        if self.inputs and len(self.inputs) > 0:
            self.set_focus(self.inputs[0])
        
    async def on_select_changed(self, event: Select.Changed) -> None:
        self.selected_project_id = event.value
        # Store the project name for display purposes
        for project in self.projects:
            if project['id'] == self.selected_project_id:
                self.selected_project_name = project['clientName']
                break
                
        await self.refresh_ui_with_data()
    
    def format_minutes(self, minutes):
        """Convert minutes to a formatted string (e.g., 90 -> 1.5)"""
        if minutes == 0:
            return ""
        hours = minutes / 60
        # Format with one decimal place if needed, otherwise as integer
        if hours.is_integer():
            return str(int(hours))
        return str(round(hours, 1))
    
    def save_default_project(self):
        """Save the currently selected project as default in .env file"""
        if not self.selected_project_id:
            return
            
        # Read current .env file
        env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
        env_content = ""
        
        # Try to read existing content
        try:
            with open(env_path, 'r') as f:
                env_content = f.read()
        except FileNotFoundError:
            pass
            
        # Update or add DEFAULT_PROJECT_ID
        if "DEFAULT_PROJECT_ID" in env_content:
            lines = env_content.splitlines()
            updated_lines = []
            for line in lines:
                if line.startswith("DEFAULT_PROJECT_ID="):
                    updated_lines.append(f"DEFAULT_PROJECT_ID={self.selected_project_id}")
                else:
                    updated_lines.append(line)
            env_content = "\n".join(updated_lines)
        else:
            if env_content and not env_content.endswith("\n"):
                env_content += "\n"
            env_content += f"DEFAULT_PROJECT_ID={self.selected_project_id}\n"
            
        # Write back to file
        with open(env_path, 'w') as f:
            f.write(env_content)

    async def reset_ui(self) -> None:
        """Completely reset and rebuild the UI"""
        # Remove all widgets first
        self.query("*").remove()
        
        # Add the basic elements
        header = Header()
        self.mount(header)
        
        # Create the project selector with a dynamic ID
        options = [(p['clientName'], p['id']) for p in self.projects]
        
        # Create select with proper prompt text that shows selected project name
        prompt = "Select"
        if self.selected_project_name:
            prompt = self.selected_project_name
            
        project_select = Select(
            options=options, 
            id=self._select_id,
            prompt=prompt
        )
        
        if self.selected_project_id:
            # We need to find the matching index to ensure the dropdown shows the right value
            for i, (name, id) in enumerate(options):
                if id == self.selected_project_id:
                    project_select.value = id
                    project_select.highlighted = i
                    break
        
        self.mount(project_select)
        
        # Add the week content if a project is selected
        if self.selected_project_id:
            week = get_week_dates(self.week_offset)
            
            # Week label with project name, centered
            label_text = f"Week: {week[0].strftime('%b %d')} - {week[-1].strftime('%b %d')}"
            if self.selected_project_name:
                label_text = f"{self.selected_project_name} - {label_text}"
                
            week_label = Static(label_text, id=self._week_label_id, classes="centered")
            self.mount(week_label)
            
            # Day inputs
            days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
            self.inputs = []
            day_inputs = []
            for i, day in enumerate(days):
                date = week[i]
                disabled = is_future_date(date)
                prefill_value = ""
                if date in self.prefilled_hours:
                    prefill_value = self.format_minutes(self.prefilled_hours[date])
                inp_id = f"day_{i}_{uuid.uuid4().hex[:6]}"
                inp = Input(placeholder=day, id=inp_id, value=prefill_value, disabled=disabled)
                self.inputs.append(inp)
                day_inputs.append(inp)
            
            horizontal = Horizontal(*day_inputs, id=self._horizontal_id)
            self.mount(horizontal)
        
        # Add footer
        footer = Footer()
        self.mount(footer)

    def compose(self) -> ComposeResult:
        yield Header()
        
        options = [(p['clientName'], p['id']) for p in self.projects]
        prompt = "Select"
        if self.selected_project_name:
            prompt = self.selected_project_name
            
        select = Select(
            options=options, 
            id=self._select_id,
            prompt=prompt
        )
        
        if self.selected_project_id:
            select.value = self.selected_project_id
            
        yield select

        yield Footer()
    
    # Action methods for key bindings
    
    async def action_prev_week(self) -> None:
        """Navigate to the previous week"""
        self.week_offset -= 1
        if self.selected_project_id:
            await self.refresh_ui_with_data()
            
    async def action_next_week(self) -> None:
        """Navigate to the next week"""
        self.week_offset += 1
        if self.selected_project_id:
            await self.refresh_ui_with_data()
            
    async def action_set_default(self) -> None:
        """Set current project as default"""
        if self.selected_project_id:
            self.save_default_project()
            self.notify("Default project set!")
            
    async def action_submit(self) -> None:
        """Submit hours for the current week"""
        await self.submit_hours()
            
    async def action_handle_escape(self) -> None:
        """Handle escape key: go back or exit"""
        focused = self.focused
        if focused and any(inp == focused for inp in self.inputs):
            # If focus is on an input, move focus back to project select
            self.set_focus(self.query_one(f"#{self._select_id}"))
        else:
            # Otherwise exit the application
            self.exit()

    async def submit_hours(self):
        """Submit hours for the current week"""
        if not self.selected_project_id:
            return
        project_id = self.selected_project_id
        week = get_week_dates(self.week_offset)
        changes_made = False
        
        for i, inp in enumerate(self.inputs):
            date = week[i]
            val = inp.value.strip()
            if inp.disabled:  # Skip future dates
                continue
                
            minutes = self.parse_hours(val)
            
            # Check if we had a previous value for this day
            had_previous_value = date in self.prefilled_hours and self.prefilled_hours[date] > 0
            
            # Only make API calls if there's a change
            if minutes == 0 and had_previous_value:
                # Delete existing entry if the new value is 0
                self.api.delete_time_entry(project_id, date)
                changes_made = True
            elif minutes > 0:
                # Submit only if the value has changed
                if not had_previous_value or minutes != self.prefilled_hours[date]:
                    self.api.book_time(project_id, date, minutes)
                    changes_made = True
        
        # Only refresh UI if changes were made
        if changes_made:
            await self.refresh_ui_with_data()
            self.notify("Hours submitted successfully!")
        else:
            self.notify("No changes to submit")

    def parse_hours(self, text):
        """Convert hours text input to minutes"""
        if not text:
            return 0
            
        # Replace comma with dot for decimal
        text = text.replace(",", ".")
        
        try:
            # Try to parse as float
            hours = float(text)
            # Convert hours to minutes (rounded to nearest minute)
            return round(hours * 60)
        except ValueError:
            return 0

    async def on_mount(self) -> None:
        """Called when app is mounted"""
        # If there's a default project selected, initialize the UI
        if self.selected_project_id:
            await self.refresh_ui_with_data()

if __name__ == "__main__":
    app = ClockifyTUI()
    try:
        asyncio.run(app.run())
    except Exception as e:
        # Handle any exceptions to ensure clean exit
        exit(0)
