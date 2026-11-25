"""Calendar read adapter and reviewable draft payload; deliberately no insert/send method."""
from datetime import datetime
import hashlib

class CalendarAdapter:
    def __init__(self,credentials):
        from googleapiclient.discovery import build
        self.service=build('calendar','v3',credentials=credentials,cache_discovery=False)
    def free_busy(self,calendar_id,start,end):
        return self.service.freebusy().query(body={'timeMin':start,'timeMax':end,'items':[{'id':calendar_id}]}).execute()
    @staticmethod
    def draft(operation_id,start,end,timezone):
        if datetime.fromisoformat(start).tzinfo is None or datetime.fromisoformat(end).tzinfo is None:raise ValueError('Timezone-aware times required')
        return {'id':hashlib.sha256(operation_id.encode()).hexdigest(), 'summary':'Technical interview',
                'start':{'dateTime':start,'timeZone':timezone},'end':{'dateTime':end,'timeZone':timezone},
                'description':'DRAFT ONLY: candidate confirmation and recruiter authorization required before booking.'}
