import sys
print(sys.path)

from kanban import db
db.create_all()

