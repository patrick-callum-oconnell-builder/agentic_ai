import json
from datetime import datetime, timedelta

async def get_calendar_events(service, time_min=None, time_max=None, max_results=10):
    """Get calendar events for the next 7 days."""
    try:
        if not time_min:
            time_min = datetime.utcnow().isoformat() + 'Z'
        if not time_max:
            time_max = (datetime.utcnow() + timedelta(days=7)).isoformat() + 'Z'

        events_result = service.events().list(
            calendarId='primary',
            timeMin=time_min,
            timeMax=time_max,
            maxResults=max_results,
            singleEvents=True,
            orderBy='startTime'
        ).execute()

        events = events_result.get('items', [])
        if not events:
            return "No upcoming events found."

        formatted_events = []
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            end = event['end'].get('dateTime', event['end'].get('date'))
            formatted_events.append({
                'summary': event['summary'],
                'start': start,
                'end': end,
                'location': event.get('location', 'No location specified')
            })

        return json.dumps(formatted_events, indent=2)
    except Exception as e:
        print(f"Error getting calendar events: {str(e)}")
        return "I apologize, but I encountered an issue while trying to fetch your calendar events. Please try again later." 