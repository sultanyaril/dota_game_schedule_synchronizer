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
TEAM_NAME = "Team Spirit"
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

    # Find match elements (adjust CSS selectors based on actual structure)
    upcoming_matches = soup.find('div', class_='fo-nttax-infobox panel')
    if not upcoming_matches:
        return matches

    for match_table in upcoming_matches.find_all("table"):
        teams_info, match_info = match_table.find_all('tr')
        team_left = teams_info.find("td", class_="team-left")
        team_right = teams_info.find("td", class_="team-right")

        first_team_name = team_left.find("span", class_="team-template-text").text if team_left.find("span", class_="team-template-text") else "TBD"
        second_team_name = team_right.find("span", class_="team-template-text").text if team_right.find("span", class_="team-template-text") else "TBD"
        time_info = match_info.find("span", class_="timer-object timer-object-countdown-only")
        start_time = datetime.utcfromtimestamp(int(time_info['data-timestamp']))

        matches.append({
            'summary': f'{first_team_name} vs {second_team_name}',
            'start': start_time,
            'end': start_time + timedelta(hours=3)
        })
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
