#!/usr/bin/env python3

'''Autogenerated SQL commands for creating an SQL database
TODO:
- have James redo schema
- add location table (all info is available in course['location'])
- make bookstore_link a property of course instead of section
- compare section attribute to course attribute and remove if same
- ask brady if we care about registration start
'''

import sqlite3
import csv

TABLES = {'class': ["title tinytext",
                    "department char(4)",
                    "code varchar(4)",
                    "description text",
                    "credits tinyint(1)",
                    "attributes text",
                    "level tinytext",
                    "type tinytext",
                    "course_link tinytext UNIQUE",
                    # NOTE: not unique because course could be crosslisted
                    "all_sections tinytext"],
          'department': ["code char(4) PRIMARY KEY",
                         "description tinytext"],
          'instructor': ["name tinytext PRIMARY KEY",
                         "email tinytext"],
          'semester': ["id char(6) PRIMARY KEY",
                       "startDate date",
                       "endDate date",
                       'registrationStart data',
                       "registrationEnd date"],
          'location': ["id smallint PRIMARY KEY",
                       "building tinytext",
                       "room smallint"],
                      # NOTE: unique within a semester, duplicated across semesters
          'section': ["uid tinyint(5)",
                      "section_link tinytext UNIQUE",
                      "section tinytext",
                      "department char(4)",
                      "code varchar(5)",
                      "semester char(6)",
                      "attributes tinytext",
                      "campus tinytext",
                      'type tinytext',
                      'method tinytext',
                      'catalog_link tinytext',
                      'bookstore_link tinytext',
                      "syllabus tinytext",
                      "days varchar(7)",
                      "location smallint",
                      "startTime time",
                      "endTime time",
                      "instructor tinytext",
                      "finalExam dateTime"],
                      # always out of date; requires parsing different page
                      #"capacity tinyint", "remaining tinyint"
          'grade': ['semester char(6)',
                    'department char(4)',
                    'code varchar(5)',
                    'title tinytext',
                    'section tinytext',
                    'campus tinytext',
                    'A tinyint',
                    '"B+" tinyint',
                    'B tinyint',
                    '"C+" tinyint',
                    'C tinyint',
                    '"D+" tinyint',
                    'D tinyint',
                    'F tinyint',
                    'AUDIT tinyint',
                    'W tinyint',
                    'WF tinyint',
                    # columns after this are questionable
                    'A_GF tinyint',
                    '"B+_GF" tinyint',
                    'B_GF tinyint',
                    '"C+_GF" tinyint',
                    'C_GF tinyint',
                    '"D+_GF" tinyint',
                    'D_GF tinyint',
                    'F_GF tinyint',
                    'S tinyint',
                    'U tinyint',
                    'UN tinyint',
                    'INCOMPLETE tinyint',
                    '"No Grade" tinyint',
                    'NR tinyint',
                    'T tinyint',
                    'FN tinyint',
                    'IP tinyint',
                    'TOTAL tinyint'
                   ]
         }


def csv_insert(table, file_name, cursor):
    with open(file_name) as f:
        # TODO: use a dict reader?
        reader = csv.reader(f)
        # TODO: check if this matches table
        headers = tuple(map(lambda s: repr(s.strip()), next(reader)))
        command = 'INSERT INTO %s (%s) VALUES (%s)'
        command %= table, ', '.join(headers), ', '.join('?' * len(headers))
        cursor.executemany(command, reader)


def create(catalog='catalog.csv', departments='departments.csv',
               instructors='instructors.csv', semesters='semesters.csv',
               sections='sections.csv', grades='grades.csv',
               database='../classes.sql'):
    '''TODO: accept parameters for file IO'''
    with sqlite3.connect(database) as DATABASE:
        CURSOR = DATABASE.cursor()

        command = ''.join('CREATE TABLE %s(%s);' % (key, ', '.join(value))
                          for key, value in TABLES.items())
        CURSOR.executescript(command)

        csv_insert('class', catalog, CURSOR)
        csv_insert('department', departments, CURSOR)
        csv_insert('instructor', instructors, CURSOR)
        csv_insert('semester', semesters, CURSOR)
        csv_insert('section', sections, CURSOR)
        csv_insert('grade', grades, CURSOR)


def limited_query(database='classes.sql', table='section', columns='*', **filters):
    '''NOTE: Does NOT validate input, that is the responsibility of calling code.
    Fails noisily if args are incorrect. Example: query_sql.py --department CSCE CSCI'''
    # ex: subject IN ('CSCE', 'CSCI') AND CRN IN (12345, 12346)
    query_filter = ' AND '.join([key + ' IN (%s)' % str(value)[1:-1].replace("'", '"')
                                 for key, value in filters.items()])
    command = 'SELECT %s FROM %s%s;' % (', '.join(columns), table,
                                        ' WHERE ' + query_filter if query_filter != '' else '')
    with sqlite3.connect(database) as DATABASE:
        return DATABASE.execute(command).fetchall()


def query(sql_query, database='classes.sql'):
    '''Return the result of an sql query exactly as if it had been passed to the sqlite3 binary'''
    with sqlite3.connect(database) as DATABASE:
        return '\n'.join('|'.join(map(str, t))
                         for t in DATABASE.execute(sql_query).fetchall())


def dump():
    print('\n'.join(query("SELECT * FROM " + table) for table in TABLES))
