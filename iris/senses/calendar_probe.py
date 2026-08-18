"""Read-only EventKit Calendar smoke test."""
from EventKit import EKEventStore, EKAuthorizationStatusFullAccess, EKEntityTypeEvent
import threading

def main():
 store=EKEventStore.alloc().init()
 status=EKEventStore.authorizationStatusForEntityType_(EKEntityTypeEvent)
 if status != EKAuthorizationStatusFullAccess:
  done=threading.Event(); result=[]
  def completed(granted, error):
   result.append(granted); done.set(); return None
  store.requestFullAccessToEventsWithCompletion_(completed)
  done.wait(30)
  if not result or not result[0]: print("Calendar access was not granted."); return 1
 calendars=store.calendarsForEntityType_(EKEntityTypeEvent)
 print(f"Calendar read-only access verified ({len(calendars)} calendars)."); return 0
if __name__ == "__main__": raise SystemExit(main())
