#!/usr/bin/env python

'''Autogenerated SQL commands for creating an SQL database'''

# dictionaries are insertion ordered; see https://stackoverflow.com/q/39980323
# therefore, PLEASE do not change this order without also modifying parse.py (or mucking around in main)
# (this happened because I was lazy in the main portion) - JN
TABLES = {'class': ["course_link tinytext",
                    "title tinytext",
                    "department char(4)",
                    "code varchar(4)",
                    "description text",
                    "credits tinyint(1)",
                    "attributes text",
                    "level tinytext",
                    "type tinytext",
                    "all_sections tinytext"],
          'department': ["abbr char(4)",
                         "title tinytext"],
          'instructor': ["name tinytext",
                         "email tinytext"],
          'semester': ["id char(6)",
                       "startDate date",
                       "endDate date",
                       'registrationStart data',
                       "registrationEnd date"],
          'location': ["uid smallint",
                       "building tinytext",
                       "room smallint"],
          'section': ["section_link",
                      "uid tinyint(5)",
                      "section tinytext",
                      "department char(4)",
                      "code varchar(4)",
                      "semester char(6)",
                      "attributes tinytext",
                      "campus tinytext",
                      'type tinytext',
                      'method tinytext',
                      'catalog_link',
                      'bookstore_link',
                      "syllabus tinytext",
                      "days varchar(7)",
                      "location smallint",
                      "startTime time",
                      "endTime time",
                      "instructor tinytext",  # this is by email, not name (since email is unique)
                      "finalExam dateTime"]
                      # always out of date; requires parsing different page
                      #"capacity tinyint", "remaining tinyint"
       }

if __name__ == '__main__':
    import sqlite3 as sql
    from utils import load

    CLASSES, DEPARTMENTS = load('.courses.data')
    SECTIONS = load('.sections.data')

    DATABASE = sql.connect('classes.sql')
    CURSOR = DATABASE.cursor()

    base = 'CREATE TABLE %s(%s);'
    CURSOR.executescript(''.join(base % (key, ', '.join(TABLES[key]))
                                 for key in TABLES.keys()))

    CURSOR.executemany('INSERT INTO class VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                      (tuple(c.values()) for c in CLASSES))

    CURSOR.executemany('INSERT INTO department VALUES (?, ?)',
                       tuple(DEPARTMENTS.items()))
    CURSOR.executemany('INSERT INTO instructor VALUES (?, ?)',
                       set((s.pop('instructor'), s['instructor_email'])
                           for s in SECTIONS))
    CURSOR.executemany('INSERT INTO semester VALUES (?, ?, ?, ?)',
                       set((s['semester'], s.pop('start_date'), s.pop('end_date'),
                           s.pop('registration_start'), s.pop('registration_end'))
                           for s in SECTIONS))
    # didn't feel like typing
    CURSOR.executemany('INSERT INTO section VALUES (%s)' %
                       ', '.join('?' * len(TABLES['section'])),
                        # final exam not done yet
                       (tuple(s.values()) + ('None',) for s in SECTIONS))
    DATABASE.commit()
    DATABASE.close()
