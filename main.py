import os
import datetime
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


import json

# Load environment variables
GOOGLE_CREDENTIALS_FILE = 'credentials.json'
TEAM_NAME = "PARIVISION"
LIQUIPEDIA_URL = f'https://liquipedia.net/dota2/{"_".join(TEAM_NAME.split(" "))}'
# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/calendar"]


def get_calendar_service():
    try:
        creds = service_account.Credentials.from_service_account_info(
            json.loads(os.environ["CREDENTIALS"]),
            scopes=SCOPES
        )
        service = build("calendar", "v3", credentials=creds)
        return service
    except HttpError as error:
        print(f"An error occurred: {error}")
        return None


# Parse Liquipedia for upcoming matches
def get_upcoming_matches():
    headers = {'User-Agent': 'Mozilla/5.0'}
    response = requests.get(LIQUIPEDIA_URL, headers=headers)
    soup = BeautifulSoup(response.content, 'html.parser')

    matches = []

    # Find all carousel items containing match information
    carousel_items = soup.find_all('div', class_='carousel-item')
    
    for carousel_item in carousel_items:
        try:
            # Extract timestamp from timer-object
            timer_object = carousel_item.find('span', class_='timer-object')
            if not timer_object or not timer_object.get('data-timestamp'):
                continue
            
            timestamp = int(timer_object['data-timestamp'])
            start_time = datetime.utcfromtimestamp(timestamp)
            
            # Extract team names from match-info-opponent-row divs
            opponent_rows = carousel_item.find_all('div', class_='match-info-opponent-row')
            if len(opponent_rows) < 2:
                continue
            
            # Get team names from span.name within each opponent row
            team_names = []
            for opponent_row in opponent_rows[:2]:  # Take first 2 teams
                name_span = opponent_row.find('span', class_='name')
                if name_span:
                    team_name = name_span.get_text(strip=True)
                    team_names.append(team_name)
                else:
                    team_names.append('TBD')
            
            if len(team_names) < 2:
                continue
            
            matches.append({
                'summary': f'{team_names[0]} vs {team_names[1]}',
                'start': start_time,
                'end': start_time + timedelta(hours=3)
            })
        except (AttributeError, ValueError, IndexError):
            # Skip matches that don't have required data
            continue
    
    return matches


# Create or get calendar
def get_or_create_calendar(service, calendar_summary):
    # Check if calendar exists
    calendar_list = service.calendarList().list().execute()
    for calendar_entry in calendar_list.get('items', []):
        if calendar_entry['summary'] == calendar_summary:
            return calendar_entry['id']

    # Create new calendar
    calendar = {
        'summary': calendar_summary,
        'timeZone': 'UTC'
    }
    created_calendar = service.calendars().insert(body=calendar).execute()
    return created_calendar['id']


# Clear all events in a calendar
def clear_calendar(service, calendar_id):
    now = (datetime.utcnow() - timedelta(days=2)).isoformat() + 'Z'
    events = service.events().list(calendarId=calendar_id, timeMin=now).execute()
    for event in events.get('items', []):
        service.events().delete(calendarId=calendar_id, eventId=event['id']).execute()


# Add match to calendar
def add_match_to_calendar(service, calendar_id, match):
    print(match['start'].isoformat())
    event = {
        'summary': match['summary'],
        'start': {'dateTime': match['start'].isoformat(), 'timeZone': 'UTC'},
        'end': {'dateTime': match['end'].isoformat(), 'timeZone': 'UTC'}
    }
    service.events().insert(calendarId=calendar_id, body=event).execute()


if __name__ == '__main__':
    service = get_calendar_service()
    matches = get_upcoming_matches()

    if service and matches:
        calendar_name = f"{TEAM_NAME} Matches"
        calendar_id = os.environ["CALENDAR_ID"]
        clear_calendar(service, calendar_id)
        for match in matches:
            add_match_to_calendar(service, calendar_id, match)
        print(f"Added {len(matches)} matches to '{calendar_name}' calendar.")
    else:
        print("No matches found or failed to connect to Google Calendar API.")
