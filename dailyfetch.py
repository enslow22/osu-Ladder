import datetime
import os
from ORM import ORM

today = datetime.date.today()
filename = str(today)
c = 0
orm = ORM()

while os.path.exists('logs/%s_%s.txt' % (filename, str(c))):
    c += 1
filename = '%s_%s.txt' % (filename, str(c))

with open('logs/%s' % filename, 'w') as f:
    try:
        summary = orm.daily_update_all()
        f.write(str(datetime.datetime.now())+'\n')
        for line in summary:
            f.write(str(line)+'\n')
        f.write('All good !')
    except Exception as e:
        f.write(str(e))
    f.close()
