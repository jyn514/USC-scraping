#!/usr/bin/env python3

'''HTML parsing. Generally, works only on files, not on strings'''

from __future__ import print_function, generators
from tempfile import mkstemp  # used for downloading seats remaining
from sys import stdout, stderr
import csv
import re  # used for only very basic stuff

from lxml import etree
from requests import get

from gradeforge.utils import save, army_time, parse_semester, parse_days

BASE_URL = 'https://ssb.onecarolina.sc.edu'

def parse_catalog(file_handle, catalog_output='courses.csv',
                  department_output='departments.csv'):
    '''
    file -> (classes, departments)
        where classes = [c...]
            where c.keys() = ('course_link', 'title', 'department', 'code',
                              'description', 'credits', 'attributes', 'level',
                              'type', 'all_sections')
        where departments = {short: long for header in html}
    TODO: lots
    - seperate prereqs from description
    - 'type' is not picked up if inside an anchor; the current mess doesn't do what I thought
    - general screwy stuff
        - description
        - departments
    - restrictions need to be subparsed, I think they're currently in attributes -JN
        - prerequisites
        - min grades
        - campus
        - colleges
        - classification (Freshman, etc.)
        - other
    '''
    if not hasattr(catalog_output, 'write'):
        with open(catalog_output, 'w') as writable:
            parse_catalog(file_handle, writable, department_output)
            return

    if not hasattr(department_output, 'write'):
        with open(department_output, 'w') as writable:
            parse_catalog(file_handle, catalog_output, writable)
            return


    catalog_headers = ('course_link', 'title', 'department', 'code', 'description',
                       'credits', 'attributes', 'level', 'type', 'all_sections')
    catalog = csv.DictWriter(catalog_output, catalog_headers)
    catalog.writeheader()

    departments = {}

    doc = etree.parse(file_handle, parser=etree.HTMLParser())
    rows = doc.xpath('/html/body//table[@class="datadisplaytable" and @width="100%"]/tr')
    HEADER = True

    for row in rows:
        if HEADER:
            anchor = row.find('td').find('a')
            course = {'course_link': anchor.attrib['href']}
            # some courses have '-' in title
            header_text = anchor.text.split(' - ')
            course_id, course['title'] = header_text[0], ' - '.join(header_text[1:])
            course['department'], course['code'] = course_id.split(' ')
        else:
            td = row.xpath('td')[0]
            course['description'] = td.text.strip()
            course['credits'] = td.xpath('br[1]/following-sibling::text()')[0]
            spans = td.xpath('span/following-sibling::text()')
            spans = tuple(map(lambda s: s.replace('\n', ''), filter(lambda s: s != '\n', spans)))
            if len(td.xpath('span')) == 3:  # has attributes
                course['attributes'] = spans[-1]
                spans = spans[:-1]
            # type can be multiple (since there might be anchor in middle)
            course['level'], course['type'], department_description = spans[0], ''.join(spans[1:-1]), spans[-1]
            if course['department'] in departments.keys() and departments[course['department']] != department_description:
                print("WARNING: incompatible description for department '%s' (new: '%s', overwrites old: '%s')"
                      % (course['department'], department_description, departments[course['department']]),
                      file=stderr)
            elif 'Department' not in department_description:
                print("WARNING: invalid department '%s' for %s" % (department_description, course['department']),
                      file=stderr)
            else:
                departments[course['department']] = department_description.replace('Department', '').strip()

            a = td.find('a')
            if a is not None:
                course['all_sections'] = a.attrib['href']
            catalog.writerow(clean_catalog(course))
            del course
        HEADER = not HEADER

    department = csv.writer(department_output)
    department_output.write('code,description\n')
    for i in departments.items():
        department.writerow(i)


def clean_catalog(course):
    '''Make elements of dict predictable'''
    if course['course_link'].startswith('/'):
        course['course_link'] = BASE_URL + course['course_link']
    # ex: '7.000    OR  8.000 Credit hours' -> '7 TO 8'
    course['credits'] = re.sub(' +(TO|OR) +', ' TO ',
                               course['credits'].replace('Credit hours', '')
                               .replace('.000', '')
                               .strip())
    try:
        course['attributes']
    except KeyError:
        course['attributes'] = None
    try:
        if course['all_sections'].startswith('/'):
            course['all_sections'] = BASE_URL + course['all_sections']
    except KeyError:
        course['all_sections'] = None
    return course


def parse_sections(file_handle, instructor_output='instructors.csv',
                   semester_output='semesters.csv', section_output='sections.csv'):
    '''file_handle -> None
            where c is dictionary with keys (section_link, UID, section, department,
            code, registration_start, registration_end, semester, attributes,
            campus, type, method, catalog_link, bookstore_link, syllabus,
            days, location, start_time, end_time, start_date, end_date,
            instructor, instructor_email
    Parses sections of a course
    Essentially a giant finite state autonoma

    Working:
    - bookstore link
    - catalog link
    - section link
    - level (UG, grad, etc.)
    - registration start
    - registration end
    - department
    - code
    - UID (CRN code)
    - semester
    - instructor
    - email
    - start date
    - end date
    - location
    - start time
    - end time
    - days (of the week)
    - type (?? only seen this to be class)
    - attributes

    Not implemented:
    - final exam (not always present; should ideally get from academic calendar)
    - books (this is implemented, just not called in follow_links)
    - seat capacity: section_link
    - seats remaining: section_link (see also https://github.com/jyn514/GradeForge/issues/9)

    TODO:
    - figure out why start_date and end_date are sometimes the same
    - department is overwritten by last seen, so there's a lot of stuff specific to upstate
    - remove 'Department' from departments
    - fix misc screwiness
    - term is different from semester, i.e. a course over summer can be three or six weeks
        TODO: organize start_date/end_date by term, not semester
    '''

    if not hasattr(instructor_output, 'write'):
        with open(instructor_output, 'w') as writable:
            parse_sections(file_handle, writable, semester_output, section_output)
            return

    if not hasattr(semester_output, 'write'):
        with open(semester_output, 'w') as writable:
            parse_sections(file_handle, instructor_output, writable, section_output)
            return

    if not hasattr(section_output, 'write'):
        with open(section_output, 'w') as writable:
            parse_sections(file_handle, instructor_output, semester_output, writable)
            return

    headers = ('section_link', 'department', 'code', 'section', 'UID', 'semester', 'campus',
               'type', 'method', 'catalog_link', 'bookstore_link', 'days',
               'location', 'startTime', 'endTime', 'instructor', 'syllabus', 'attributes')
    sections = csv.DictWriter(section_output, headers)
    sections.writeheader()

    # these allow constant-time lookups to see if a key is already present,
    # as opposed to sets, which require linear search
    # the reason for lookups is because the parsing is still imperfect;
    # this allows warning when a key already exists in the dict
    semester_dict = {}
    instructor_dict = {}

    doc = etree.parse(file_handle, etree.HTMLParser())
    rows = doc.xpath('/html/body//table[@class="datadisplaytable" and @width="100%"][1]/tr[position() > 2]')
    assert len(rows) % 2 == 0  # even
    HEADER = True
    for row in rows:
        if HEADER:
            anchor = row.xpath('th/a[1]')[0]  # etree returns list even if only one element
            course = {'section_link': anchor.attrib.get('href')}
            text = anchor.text.split(' - ')
            # everything before last three is title
            course['UID'], course_id, course['section'] = text[-3:]
            course['department'], course['code'] = course_id.split(' ')
        else:
            main = row.xpath('td[1]')[0]

            after = main.xpath('span/following-sibling::text()')
            after = tuple(map(lambda x: x.strip(), filter(lambda x: x != '\n', after)))

            semester = {}
            semester_raw, registration = after[:2]  # third is level, which we know
            course['semester'] = parse_semester(*semester_raw.split(' '))
            semester['registrationStart'], semester['registrationEnd'] = registration.split(' to ')

            if len(after) == 8:
                course['attributes'] = after[3]
            campus, schedule_type, method = after[-4:-1]  # last is credits
            course['campus'] = campus.replace('USC ', '').replace(' Campus', '')
            course['type'] = schedule_type.replace(' Schedule Type', '')
            course['method'] = method.replace(' Instructional Method', '')

            links = main.xpath('a/@href')
            course['catalog_link'], course['bookstore_link'] = links[-2:]
            if len(links) == 3:
                course['syllabus'] = links[0]

            table_info = main.xpath('table/tr[2]/td//text()')
            if len(table_info) == 9:  # instructor exists
                table_info = table_info[:-2]  # don't get junk at end
            elif len(table_info) > 9:  # multiple instructors
                # combine instructors into one element
                table_info = table_info[:6] + [''.join([table_info[7]] + table_info[9:])]
            if not table_info:  # independent study; this is handled on the frontend
                for key in ['days', 'location', 'startTime', 'endTime',
                            'instructor']:
                    course[key] = None
                email, semester['startDate'], semester['endDate'] = [None] * 3
            else:
                _, times, course['days'], course['location'], dates, _, course['instructor'] = table_info
                course['instructor'] = re.sub(' +', ' ', course['instructor'].strip().replace(' (', ''))
                if times == 'TBA':
                    course['startTime'], course['endTime'] = 'TBA', 'TBA'
                else:
                    course['startTime'], course['endTime'] = map(army_time, times.split(' - '))
                semester['startDate'], semester['endDate'] = dates.split(' - ')
                try:
                    # str is necessary, otherwise returns _ElementUnicodeResult
                    email = str(main.xpath('table/tr[2]/td/a/@href')[0])
                except IndexError:
                    email = None
            try:
                if email != instructor_dict[course['instructor']]:
                    print("WARNING: email '%s' for instructor '%s' already exists and does not match '%s'"
                          % (instructor_dict[course['instructor']], course['instructor'], email),
                          file=stderr)
            except KeyError:
                instructor_dict[course['instructor']] = email
            try:
                if tuple(semester_dict[course['semester']].values()) != tuple(semester.values()):
                    print("WARNING: semester info '%s' already exists for semester '%s' and does not match '%s'"
                          % (semester_dict[course['semester']], course['semester'], semester),
                          file=stderr)
            except KeyError:
                semester_dict[course['semester']] = semester
            sections.writerow(clean_section(course))
            # error instead of silently addding wrong info when rows/headers out of order
            del course
        HEADER = not HEADER

    instructors = csv.writer(instructor_output)
    instructor_output.write('name, email\n')
    instructors.writerows(instructor_dict.items())

    headers = 'id', 'startDate', 'endDate', 'registrationStart', 'registrationEnd'
    semesters = csv.DictWriter(semester_output, headers)
    semesters.writeheader()
    semesters.writerows(dict({'id': key}, **values)
                        for key, values in semester_dict.items())



def clean_section(course):
    '''Make course elements more predictable'''
    try:
        if course['syllabus'].startswith('/'):
            course['syllabus'] = BASE_URL + course['syllabus']
    except KeyError:
        course['syllabus'] = None
    try:
        course['attributes']
    except KeyError:
        course['attributes'] = None
    for key in ('catalog_link', 'bookstore_link', 'section_link'):
        if course[key].startswith('/'):
            course[key] = BASE_URL + course[key]
    return course


def parse_exam(file_handle, output=stdout):
    '''Writes a csv to `output`, with headers.
    Quite fast compared to parse_sections, but it's handling less data.

    Params:
        - file_handle: str or implements `read`
        - semester: the semester to use for every exam in the csv.
                    default is to infer from file_handle name.
                    custom is to use USC semester (use utils.parse_semester).
        - output: same type as file_handle, where to write the csv
    '''
    if not hasattr(output, 'write'):
        with open(output, 'w') as writable:
            parse_exam(file_handle, writable)
            return

    doc = etree.parse(file_handle, etree.HTMLParser())

    title = doc.xpath('/html/head/title/text()')[0]
    semester = title.split(' - ')[0].replace('Final Exam Schedule ', '')
    semester = parse_semester(*semester.split(' '))

    div = doc.xpath('/html/body/section/div/div/section[2]/div/section/div/div/section')[0]
    csv_headers = 'semester', 'days', 'time_met', 'exam_date', 'exam_time'
    writer = csv.DictWriter(output, csv_headers)
    writer.writeheader()

    headers = div.xpath('div[@class="accordion-summary"]/h5')
    bodies = div.xpath('div[@class="accordion-details"]/table/tbody')
    for i, header in enumerate(headers):
        try:
            days_met = parse_days(header.text)
        # given session, not days. Ex: 'Spring I (3A) and Spring II (3B)'
        except KeyError:
            days_met = 'any'  # TODO
        for row in bodies[i].findall('tr'):
            current = {'semester': semester, 'days': days_met}
            # Example: ('TR - 8:30 a.m.', 'Thursday, May 3 - 9:00 a.m.')
            # school likes to put some as spans, some not
            time_met, exam_datetime = map(lambda td: ''.join(td.itertext())
                                          .strip()
                                          .replace('\xa0', ' '),
                                          row.findall('td'))
            if exam_datetime == 'TBA':  # this is frustrating
                exam_date, exam_time = 'TBA', 'TBA'
            else:
                split = exam_datetime.split(', ')
                regex = r'\s*[–-]\s*'
                if any(map(str.isnumeric, split[0])):  # sometimes it's 'May 4th, Fri.'
                    exam_date, exam_time = split[0], split[-1]  # commma after Friday
                    try:
                        exam_time = re.split(regex, exam_time)[1]
                    except IndexError:
                        assert 'class meeting time' in exam_time.lower(), exam_time
                else:  # Friday, May 4 - 8:30 p.m.
                    exam_date, exam_time = re.split(r'\s*[–-]\s*', split[1])
                exam_date = re.sub('(th|nd|st|rd)', '', exam_date)
                try:
                    exam_time = army_time(exam_time)
                except ValueError:  # TODO: DRY
                    assert 'class meeting time' in exam_time.lower(), exam_time
            if 'all sections' in time_met.lower():
                # TODO: add post-processing
                current.update({'time_met': 'any'})
                writer.writerow(current)
            else:
                split = re.split(r'\s*[MTWRFSU]+\s+(-\s+)?', time_met)
                if days_met == 'any':
                    print(split, file=stderr)
                # example: '8:30 a.m.,11:40 a.m., 2:50 p.m., 6:00 p.m.'
                for time in re.split(', ?', split[-1]):
                    copy = current.copy()
                    copy.update({'time_met': army_time(time), 'exam_date': exam_date, 'exam_time': exam_time})
                    writer.writerow(copy)


def get_seats(section_link):
    'str -> (capacity, taken, remaining)'
    tmp_file = mkstemp()[1]
    save(get(section_link).text, tmp_file)
    body = etree.iterparse(open(tmp_file, 'rb'), html=True).__next__()[1].getparent().getnext()
    table = list(body.iterdescendants('table'))[2].iterdescendants('table').__next__()
    elements = list(list(table.iterdescendants('tr'))[1])[-3:]
    return tuple(map(lambda x: x.text, elements))


def parse_bookstore(file_handle, output=stdout):
    '''
    Output must be a file_handle, not a file path

    Implemented:
    - name
    - ISBN
    - prices
        - used rent
        - new rent
        - used buy
        - new buy
        - amazon
    - link
    - author
    - edition
    - required/recommended/optional
    '''

    if not hasattr(output, 'write'):
        with open(output, 'w') as writable:
            parse_bookstore(file_handle, writable)
            return
    doc = etree.parse(file_handle, etree.HTMLParser())
    form = doc.xpath('/html/body/header/section/div[@class="courseMaterialsList"]/div/form[@id="courseListForm"]')[0]
    books = form.xpath('div[@class="book_sec"]/div/div[@class="book-list"]/div')

    # TODO: sometimes prices are missing. need to handle this gracefully
    headers = ('title', 'required', 'author', 'edition', 'publisher', 'isbn',
               'image', 'link', 'buy-new', 'buy-used', 'rent-new', 'rent-used')
    writer = csv.DictWriter(output, headers)
    writer.writeheader()
    for book in books:
        info = {}

        info['image'] = book.xpath('div[2]/a/img/@src')[0]

        main = book.find('div[3]')

        anchor = main.xpath('h1/a')[0]
        info['link'] = anchor.attrib['href']
        info['title'] = anchor.attrib['title']

        info['required'] = main.xpath('h2/span[@class="recommendBookType"]/text()')[0].strip().lower()
        info['author'] = main.xpath('h2/span/i/text()')[0].replace('By ', '')
        info['edition'], info['publisher'], info['isbn'] = map(lambda s: s.tail.replace('\xa0', '').replace('Â', '').strip(),
                                                               main.xpath('ul/li/strong'))
        prices = book.xpath('div[4]/div[@class="selectBookCont"]/div/ul/li[2]/ul/li')
        for p in prices:
            info[p.attrib['title'].lower().strip().replace(' ', '-')] = p.find('span').text.strip()
        writer.writerow(info)


def parse_grades(file_handle, output='grades.csv'):
    '''File_handle is assumed to contain the output of `pdftotext -layout <pdf>`'''
    if not hasattr(file_handle, 'read'):
        with open(file_handle) as readable:
            parse_grades(readable, output)
            return

    if not hasattr(output, 'write'):
        with open(output, 'w') as writable:
            parse_grades(file_handle, writable)
            return

    while True:  # sometimes header is not on first line
        metadata = next(file_handle).strip()
        metadata = re.sub(' ?GRADE ?(SPREAD FOR|DISTRIBUTION)', '', metadata)
        match = re.search('(FALL|SUMMER|SPRING)? ?([0-9]{4})', metadata, re.IGNORECASE)
        if match is not None:
            season, year = match.groups()
            break
    if season is None:
        print("WARNING: '%s' does not have enough info to parse semester, "
              % metadata + "assuming season is Spring", file=stderr)
        season = 'spring'
    semester = parse_semester(season, year)
    try:
        campus = re.search('((THE )?UNIVERSITY OF SOUTH CAROLINA ?([‐-]|at) ?|USC[‐ -])([^:]*)', metadata, flags=re.IGNORECASE)
        campus = campus.groups()[-1].replace(' CAMPUS', '').upper()
    except:
        print(metadata, file=stderr)

    while True:
        try:
            headers = next(file_handle)
        except StopIteration:
            print(file_handle, file=stderr)
            raise
        if re.match(' *DEP(ar)?T', headers, flags=re.IGNORECASE) is not None:
            headers = headers.upper()
            headers = re.sub(r'DEP(AR)?T(\.|MENT)?', 'DEPARTMENT', headers)
            headers = re.sub(r'SEC(T(ION)?)?\.?', 'SECTION', headers)
            headers = re.sub(r'C(OU)?RSE( ?#)?', 'COURSE', headers)
            headers = headers.replace('DEPARTMENT/COURSE', 'DEPARTMENT COURSE')
            headers = headers.replace('AUD', 'AUDIT')
            headers = headers.replace(' I ', ' INCOMPLETE ').split()
            break
    if len(headers) < 18:
        raise ValueError("Bad value '%s' for headers" % headers)
    output.write(','.join(['SEMESTER', 'CAMPUS'] + headers) + '\n')
    # all of these functions are generators, which require very low memory usage
    csv.writer(output).writerows(map(lambda s: [semester, campus] + s,
                                     filter(lambda l: len(l) == len(headers),
                                            map(str.split, file_handle))))

def combine_grades(output='grades.csv', *file_handles):
    '''The headers for CSV files change from file to file.
    This method normalizes headers and adds empty strings if needed.'''
    headers = 'SEMESTER,CAMPUS,DEPARTMENT,COURSE,SECTION,TITLE,A,B+,B,C+,C,D+,D,F,'
              # TODO: what the hell do these mean
    headers += 'A_GF,B+_GF,B_GF,C_GF,C+_GF,D+_GF,D_GF,F_GF,'
    headers += 'S,U,UN,INCOMPLETE,W,WF,NR,TOTAL,No Grade,T,IP,FN,AUDIT'
    with open(output, 'w') as w:
        writer = csv.DictWriter(w, headers.split(','))
        writer.writeheader()
        for handle in file_handles:
            with open(handle) as r:
                writer.writerows(csv.DictReader(r))
