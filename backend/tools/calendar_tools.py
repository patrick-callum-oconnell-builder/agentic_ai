import json
from datetime import datetime, timedelta

async def get_calendar_events(service, query=None, max_results=10):
    """Get calendar events based on the query."""
    try:
        # Use the service's get_upcoming_events method which handles time ranges properly
        events = await service.get_upcoming_events(query, max_results)
        
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
        return "I encountered an issue while fetching your calendar events. Please try again." 