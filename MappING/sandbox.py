
import datetime
from datetime import datetime, datetime, timezone, timedelta
fromisoformat = datetime.fromisoformat
def now_time(): return datetime.now(timezone.utc)

filename = "cal-filtr_" + str(now_time())[:-6].replace(" ","_") + ".ics"

print(filename)