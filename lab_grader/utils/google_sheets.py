import logging

import pickle
import os.path
from googleapiclient.discovery import build
from google.oauth2 import service_account
from google.auth.transport.requests import Request

# If modifying these scopes, delete the file token.pickle.
# We need write access to the spreadsheet: https://developers.google.com/sheets/api/guides/authorizing
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']


class GoogleSheet:
    spreadsheet = None
    sheets = None
    data = None
    data_update = None
    # some predefined constants that describe data structure
    DEFAULT_STUDENT_NAME_COLUMN = 1
    DEFAULT_LAB_COLUMN_OFFSET = 1
    DEFAULT_TASK_ID_COLUMN = 0

    # TODO: get rid of DIMENSION parameter in class methods and move it to init as a class attribute
    def __init__(self, config):
        """
        :param config: a course config
        """
        # read config params
        self.credentials_file = config['auth']['google']['credentials']
        self.spreadsheet_id = config['google']['spreadsheet']
        self.task_id_column = config['google'].get('task-id-column', self.DEFAULT_TASK_ID_COLUMN)
        self.student_name_column = config['google'].get('student-name-column',
                                                                  self.DEFAULT_STUDENT_NAME_COLUMN)
        self.lab_column_offset = config['google'].get('lab-column-offset', self.DEFAULT_LAB_COLUMN_OFFSET)
        # create a new API instance to work with the spreadsheet
        self.spreadsheet = self.__get_spreadsheet_instance()
        # load sheet names
        self.sheets = self.__get_sheet_names()
        logging.getLogger(__name__).debug("Available sheets: %s", self.sheets)
        # print(self.sheets)
        # escape sheet names:
        self.sheets = ["'{}'".format(s) for s in self.sheets]
        # load spreadsheet data into dict with sheet name as key and sheet data as value
        self.data = self.__get_multiple_sheets_data()
        # a list of pending data updates prepared for spreadsheets.values.batchUpdate request
        self.data_update = []

    @staticmethod
    def colnum_string(n, zero_based=False):
        string = ""
        if zero_based:
            n += 1
        while n > 0:
            n, remainder = divmod(n - 1, 26)
            string = chr(65 + remainder) + string
        return string

    def __get_spreadsheet_instance(self):
        """
        Performs authentication and creates a service.spreadsheets() instance

        :returns: service.spreadsheets() instance
        """
        creds = None
        # The file token.pickle stores the user's access and refresh tokens, and is
        # created automatically when the authorization flow completes for the first
        # time.
        if os.path.exists('token.pickle'):
            with open('token.pickle', 'rb') as token:
                creds = pickle.load(token)
        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                creds = service_account.Credentials.from_service_account_file(self.credentials_file, scopes=SCOPES)
            # Save the credentials for the next run
            with open('token.pickle', 'wb') as token:
                pickle.dump(creds, token)

        service = build('sheets', 'v4', credentials=creds, cache_discovery=False)

        # Call the Sheets API
        spreadsheet = service.spreadsheets()
        return spreadsheet

    def __get_sheet_names(self):
        """
        Get all sheet names that are present on the spreadsheet

        :returns: list with sheet names
        """
        sheets = []
        result = self.spreadsheet.get(
            spreadsheetId=self.spreadsheet_id
        ).execute()
        for s in result['sheets']:
            sheets.append(s.get('properties', {}).get('title'))
        return sheets

    def __get_multiple_sheets_data(self, dimension='COLUMNS'):
        """
        Get data from multiple sheets at once with a batchGet request

        :param dimension: passed to spreadsheet.values().batchGet as a value of majorDimension param. Possible values are 'COLUMNS' or 'ROWS'
        :returns: dict with sheet name as key and data as value
        """
        data = {}
        request = self.spreadsheet.values().batchGet(
            spreadsheetId=self.spreadsheet_id,
            ranges=self.sheets, majorDimension=dimension
        )
        response = request.execute()
        for i in range(0, len(response.get('valueRanges'))):
            data[self.sheets[i]] = response.get('valueRanges')[i].get('values')
        return data

    def find_column_by_name(self, col_name, sheet, dimension='COLUMNS'):
        """
        Find column id (zero-based)

        :col_name: name of the column to be searched for
        :param sheet: name of the sheet to search for the given column
        :param dimension: how the data is stored, see spreadsheet.values().batchGet
        :returns: zero-based column number of column
        """
        _column_number = None
        for i in range(0, len(self.data[sheet])):
            if col_name in self.data[sheet][i]:
                _column_number = i
                break
        # print(col_name)
        # print(self.data[sheet][3])
        return _column_number
        return _column_number

    def _find_github_column(self, student, dimension='COLUMNS'):
        """
        Find GitHub column id (zero-based)
        
        :param student: dict with a 'group' key
        :param dimension: how the data is stored, see spreadsheet.values().batchGet
        :returns: zero-based column number of GitHub column
        :raises ValueError: if GitHub column is not found
        """
        github_column = self.find_column_by_name('GitHub', student['group'])
        if github_column is None:
            raise ValueError(
                "Internal error! GitHub account column not found on sheet {}. Please, verify spreadsheet integrity!".format(
                    student['group']))
        return github_column

    def find_student(self, student, dimension='COLUMNS', searchby='name'):
        """
        Find student in data from multiple sheets. A student is described by his/her
        group and either name or github account. If both student's name and
        github account are present, the value of searchby param is used to determine
        which one of them will be used. If student's name is missing, but github
        account is present, value of searchby is ignored.

        :param student: dict with a 'group' key and one of ('name', 'github') keys
        :param dimension: how the data is stored, see spreadsheet.values().batchGet
        :param searchby: choose either 'name' or 'github' to be used for the
        search if both are used to describe the student
        :returns: row number if the student is found (zero based)
        :raises ValueError: if either group or student are not found in data
        """
        if dimension != 'COLUMNS':
            raise ValueError("Not implemented! Only 'COLUMNS' dimension value is supported at the moment.")
        if student['group'] not in self.data:
            raise ValueError(
                "Group '{}' not found in spreadsheet! Available groups are: {}. Check your spelling or contact course staff if you don't see your group listed.".format(
                    student['group'], list(self.data.keys())))
        if 'name' in student and searchby == 'name':
            try:
                position = self.data[student['group']][self.student_name_column].index(student['name'])
            except ValueError:
                raise ValueError(
                    "Student '{}' not found in group {}! Check spelling or contact course staff if you are not on the group list.".format(
                        student['name'], student['group']))
        elif 'github' in student:
            github_column = self._find_github_column(student)
            try:
                github_names = [s.lower() for s in self.data[student['group']][github_column]]
                position = github_names.index(student['github'].lower())
                # position = data[student['group']][github_column].index(student['github'])
            except ValueError:
                raise ValueError(
                    "Student with GitHub account {} not found in group {}! Check spelling or contact course staff if you are not on the group list.".format(
                        student['github'], student['group']))
        else:
            raise ValueError(
                "Internal error! Both name and github account info are missing from student description: {}".format(
                    student))
        return position

    def find_student_by_github(self, github, dimension='COLUMNS'):
        """
        Search for a student in all groups by his/her github

        :param data: dict with sheet name as key and data as value
        :param github: github account name to be searched for
        :param dimension: how the data is stored, see spreadsheet.values().batchGet
        :returns: student info as a dict with 'group', 'name', 
        'github' and 'position' keys
        :raises ValueError: if student with such github account is not found in data
        """
        position = None
        student = {'group': None, 'github': github}
        for group in self.data:
            student['group'] = group
            try:
                position = self.find_student(student, searchby='github')
            except ValueError as e:
                position = None
                pass
            if position:
                student['name'] = self.data[student['group']][self.student_name_column][position]
                student['position'] = position
                return student
        raise ValueError("Student with GitHub account {} not found in any of the groups!".format(github))

    def get_student_task_id(self, student, dimension='COLUMNS'):
        """
        Find stident's task id from google spreadsheet

        :param student: dict with at least 'name' and 'group' keys
        :param dimension: how the data is stored, see spreadsheet.values().batchGet
        :returns: task id if student is found
        :raises ValueError: if either group or student are not found in data
        """
        if dimension != 'COLUMNS':
            raise ValueError("Not implemented! Only 'COLUMNS' dimension value is supported at the moment.")
        student_position = self.find_student(student, dimension=dimension)
        task_id = self.data[student['group']][self.task_id_column][student_position]
        return task_id

    def get_student_github(self, student, dimension='COLUMNS'):
        """
        Get student's GitHub account from google spreadsheet

        :param student: dict with at least 'name' and 'group' keys
        :param dimension: how the data is stored, see spreadsheet.values().batchGet
        :returns: GitHub account name if student is found. None if student is found, but has no account
        :raises ValueError: if either group, student or GitHub column are not found in data
        """
        if dimension != 'COLUMNS':
            raise ValueError("Not implemented! Only 'COLUMNS' dimension value is supported at the moment.")
        student_position = self.find_student(student, dimension=dimension)
        github_column = self._find_github_column(student)
        student_github = None
        try:
            student_github = self.data[student['group']][github_column][student_position]
            if len(student_github.strip()) == 0:
                student_github = None
        except IndexError:
            student_github = None
        return student_github

    def get_student_lab_status(self, student, lab_id, dimension='COLUMNS'):
        """
        Get student's lab status from google spreadsheet

        :param student: dict with at least 'name' and 'group' keys
        :param lab_id: string column name or integer lab identifier (starting from 1 onwards)
        :param dimension: how the data is stored, see spreadsheet.values().batchGet
        :returns: status of lab if student is found. None if student is found, but has no status for that lab
        :raises ValueError: if either group or student are not found in data
        """
        if dimension != 'COLUMNS':
            raise ValueError("Not implemented! Only 'COLUMNS' dimension value is supported at the moment.")
        student_position = self.find_student(student, dimension=dimension)
        student_lab_status = None
        try:
            if isinstance(lab_id, str):
                lab_column = self.find_column_by_name(lab_id, student['group'])
            else:
                lab_column = self.lab_column_offset + lab_id
            # print(lab_id, student['group'], lab_column)
            student_lab_status = self.data[student['group']][lab_column][student_position]
        except (IndexError, TypeError):
            student_lab_status = None
        if student_lab_status == "":
            student_lab_status = None
        return student_lab_status

    def get_lab_deadline(self, group, lab_id, dimension='COLUMNS'):
        """
        Get deadline for a lab 

        :param group: group the deadline to retrieve for
        :param lab_id: string column name or integer lab identifier (starting from 1 onwards)
        :param dimension: how the data is stored, see spreadsheet.values().batchGet
        :returns: deadline for a given lab
        """
        if dimension != 'COLUMNS':
            raise ValueError("Not implemented! Only 'COLUMNS' dimension value is supported at the moment.")
        try:
            if isinstance(lab_id, str):
                lab_column = self.find_column_by_name(lab_id, group)
            else:
                lab_column = self.lab_column_offset + lab_id
            # print(group, lab_id, lab_column)
            lab_deadline = self.data[group][lab_column][0]
        except (IndexError, TypeError):
            lab_deadline = None
        return lab_deadline

    def set_student_github(self, student, dimension='COLUMNS'):
        """
        Set student's github account to the value specified in student param

        :param student: dict with at least 'name', 'group' and 'github' keys
        :param dimension: how the data is stored, see spreadsheet.values().batchGet
        :returns: a list of pending data update requests with appended
        request to update github account for the user in question
        :raises ValueError: if group or student not found, if github account
        for that student is already known and is different, if github account
        if already used by another student
        """
        if dimension != 'COLUMNS':
            raise ValueError("Not implemented! Only 'COLUMNS' dimension value is supported at the moment.")
        # check data for validity:
        # # 1. does this student already have a github account?
        # student_github = get_student_github(data, student, dimension=dimension)
        # if student_github is not None and student_github != student['github']:
        #     raise ValueError("GitHub account for student '{}' from group '{}' is '{}'. Can't set it to '{}'. Contact course staff if you want to update it.".format(student['name'], student['group'], student_github, student['github']))
        # # 2. does any other student already use that github account?
        other_student = None
        is_new_student = True
        try:
            other_student = self.find_student_by_github(student['github'], dimension=dimension)
        except ValueError as e:
            pass
        else:
            # 1. does any other student already use that github account?
            if other_student['group'] != student['group'] or other_student['name'] != student['name']:
                raise ValueError(
                    "Can't set GitHub account for student '{}' from group '{}' to '{}'. This GitHub account is already used by student '{}' from group '{}'. Are you trying to cheat here?".format(
                        student['name'], student['group'], other_student['github'], other_student['name'],
                        other_student['group']))
            # 2. does this student already have a github account?
            elif other_student['github'] != student['github']:
                # here we assume that other_student and student are the same person
                raise ValueError(
                    "GitHub account for student '{}' from group '{}' is '{}'. Can't set it to '{}'. Contact course staff if you want to update it.".format(
                        student['name'], student['group'], other_student['github'], student['github']))
            # 3. If not 1 & 2, then it must be a duplicate, so ignore it
            else:
                is_new_student = False
        # TODO: join validity checks 1 & 2 above to be just a single check
        # ^ seems to be done!
        if is_new_student:
            student_position = self.find_student(student, dimension=dimension, searchby='name')
            github_column = self._find_github_column(student, dimension=dimension)
            values_count = len(self.data[student['group']][github_column])
            if values_count < student_position + 1:
                self.data[student['group']][github_column] = [
                    self.data[student['group']][github_column][i] if i < values_count else "" for i in
                    range(0, student_position + 1)
                ]
            self.data[student['group']][github_column][student_position] = student['github']
            self.data_update.append({
                'range': "{}!{}{}".format(student['group'], self.colnum_string(github_column, True),
                                          student_position + 1),
                # 'majorDimension': dimension,
                'values': [[student['github']]]
            })
            # print("Pending write operation: {} @ {}".format(self.data_update[-1]['values'], self.data_update[-1]['range']))
            logging.getLogger(__name__).info("Pending write operation: %s @ %s", self.data_update[-1]['values'],
                                             self.data_update[-1]['range'])
        return self.data_update

    def set_student_lab_status(self, student, lab_id, value, dimension='COLUMNS'):
        """
        Set student's result for lab 'lab_id' to 'value'

        :param student: dict with at least 'group' and one of 'name' or 'github' keys
        :param lab_id: string column name or integer lab identifier (starting from 1 onwards)
        :param value: string value to be set as student's lab_id result
        :param dimension: how the data is stored, see spreadsheet.values().batchGet
        :returns: a list of pending data update requests with appended
        request to update github account for the user in question
        :raises ValueError: 
        """
        if dimension != 'COLUMNS':
            raise ValueError("Not implemented! Only 'COLUMNS' dimension value is supported at the moment.")
        student_position = self.find_student(student, dimension=dimension)
        if isinstance(lab_id, str):
            print(lab_id)
            lab_column = self.find_column_by_name(lab_id, student['group'])
        else:
            lab_column = self.lab_column_offset + lab_id
        print(student)
        # print(self.data)
        print(lab_column)
        print(lab_id)
        values_count = len(self.data[student['group']][lab_column])
        if values_count < student_position + 1:
            self.data[student['group']][lab_column] = [
                self.data[student['group']][lab_column][i] if i < values_count else "" for i in
                range(0, student_position + 1)
            ]
        # print(student)
        # print(lab_column, student_position, values_count, len(data[student['group']][lab_column]))
        # print(data[student['group']][lab_column])
        self.data[student['group']][lab_column][student_position] = value
        self.data_update.append({
            'range': "{}!{}{}".format(student['group'], self.colnum_string(lab_column, True), student_position + 1),
            # 'majorDimension': dimension,
            'values': [[value]]
        })
        # print("Pending write operation: {} @ {}".format(data_update[-1]['values'], data_update[-1]['range']))
        logging.getLogger(__name__).info("Pending write operation: %s @ %s", self.data_update[-1]['values'],
                                         self.data_update[-1]['range'])
        return self.data_update

    def batch_update(self):
        """
        Performs a batchUpdate query on a spreadsheet

        :returns: number of updated cells
        """
        body = {
            'valueInputOption': "RAW",
            'data': self.data_update
        }
        result = self.spreadsheet.values().batchUpdate(
            spreadsheetId=self.spreadsheet_id,
            body=body
        ).execute()
        # print('{0} cells updated.'.format(result.get('totalUpdatedCells')))
        logging.getLogger(__name__).info('%s cells updated.', result.get('totalUpdatedCells'))
        return result.get('totalUpdatedCells')


def main():
    # spreadsheet = get_spreadsheet_instance()
    # sheets = get_sheet_names(spreadsheet)
    # print(sheets)
    # #escape sheet names:
    # sheets = ["'{}'".format(s) for s in sheets]
    # data = get_multiple_sheets_data(spreadsheet, sheets)
    logging.basicConfig(
        level=logging.DEBUG,
        format='[%(asctime)s] {%(pathname)s:%(lineno)d} %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    import sys
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} SPREADSHEET_ID CREDENTIALS_FILE")
        exit()
    config = {
        'course': {'google': {'spreadsheet': sys.argv[1]}},
        'auth': {'google': {'credentials-file': sys.argv[2]}}
    }
    spreadsheet = GoogleSheet(config)
    print(f"Sheet names are: {spreadsheet.sheets}")
    # print(f"Data: {spreadsheet.data}")


if __name__ == '__main__':
    main()
