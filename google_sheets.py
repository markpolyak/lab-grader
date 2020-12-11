import settings

import pickle
import os.path
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# If modifying these scopes, delete the file token.pickle.
# We need write access to the spreadsheet: https://developers.google.com/sheets/api/guides/authorizing
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']


class StudentGoogleSheet:
    spreadsheet = None
    exemplars = []
    sheets = None
    data = None
    connected = False
    # some predefined constants that describe data structure
    # need to move it out to settings
    STUDENT_NAME_COLUMN = 1
    LAB_COLUMN_OFFSET = 1

    def __init__(self, student=None):
        self.student = student
        self.exemplars.append(self)

    @staticmethod
    def __get_spreadsheet_instance():
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
                flow = InstalledAppFlow.from_client_secrets_file(
                    settings.google_credentials_file, SCOPES)
                creds = flow.run_local_server(port=0)
            # Save the credentials for the next run
            with open('token.pickle', 'wb') as token:
                pickle.dump(creds, token)

        service = build('sheets', 'v4', credentials=creds, cache_discovery=False)

        # Call the Sheets API
        spreadsheet = service.spreadsheets()
        return spreadsheet

    @staticmethod
    def colnum_string(n, zero_based=False) -> str:
        string = ""
        if zero_based:
            n += 1
        while n > 0:
            n, remainder = divmod(n - 1, 26)
            string = chr(65 + remainder) + string
        return string

    @classmethod
    def spreadsheet_connect(cls):
        if not cls.connected:
            cls.spreadsheet = cls.__get_spreadsheet_instance()
            cls.sheets = cls.__get_sheet_names()
            print(cls.sheets)
            # escape sheet names:
            cls.sheets = ["'{}'".format(s) for s in cls.sheets]
            cls.data = cls.__get_multiple_sheets_data()
            cls.connected = True
            print(cls.data)
        else:
            print("spredsheets have been already initialized. try to access it by self.spreadsheet attr")

    @classmethod
    def __get_sheet_names(cls) -> list:
        """
        Get all sheet names that are present on the spreadsheet

        :param spreadsheet: a service.spreadsheets() instance
        :returns: list with sheet names
        """
        sheets = []
        result = cls.spreadsheet.get(spreadsheetId=settings.google_spreadsheet_id).execute()
        for s in result['sheets']:
            sheets.append(s.get('properties', {}).get('title'))
        return sheets

    @classmethod
    def __get_multiple_sheets_data(cls, dimension='COLUMNS'):
        """
        Get data from multiple sheets at once with a batchGet request

        :param spreadsheet: a service.spreadsheets() instance
        :param sheets: a list of sheet names for which the data is to be retrieved
        :param dimension: passed to spreadsheet.values().batchGet as a value of majorDimension param. Possible values are 'COLUMNS' or 'ROWS'
        :returns: dict with sheet name as key and data as value
        """
        data = {}
        request = cls.spreadsheet.values().batchGet(spreadsheetId=settings.google_spreadsheet_id,
                                                    ranges=cls.sheets,
                                                    majorDimension=dimension)
        response = request.execute()
        for i in range(0, len(response.get('valueRanges'))):
            data[cls.sheets[i]] = response.get('valueRanges')[i].get('values')
        return data

    @classmethod
    def batch_update(cls, data_update):
        """
        Performs a batchUpdate query on a spreadsheet

        :param spreadsheet: a service.spreadsheets() instance
        """
        body = {
            'valueInputOption': "RAW",
            'data': data_update
        }
        result = cls.spreadsheet.values().batchUpdate(
            spreadsheetId=settings.google_spreadsheet_id, body=body).execute()
        print('{0} cells updated.'.format(result.get('totalUpdatedCells')))
        return result.get('totalUpdatedCells')
        # raise ValueError("Not implemented!")

    def set_student_github(self, dimension='COLUMNS', data_update=[]) -> list:
        """
        Set student's github account to the value specified in student param

        :param data: dict with sheet name as key and data as value
        :param student: dict with at least 'name', 'group' and 'github' keys
        :param dimension: how the data is stored, see spreadsheet.values().batchGet
        :param data_update: a list of pending data updates prepared for
        spreadsheets.values.batchUpdate request
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
            other_student = self.find_student_by_github(self.student['github'], dimension=dimension)
        except ValueError as e:
            pass
        else:
            # 1. does any other student already use that github account?
            if other_student['group'] != self.student['group'] or other_student['name'] != self.student['name']:
                raise ValueError(
                    "Can't set GitHub account for student '{}' from group '{}' to '{}'. This GitHub account is already used by student '{}' from group '{}'. Are you trying to cheat here?".format(
                        self.student['name'], self.student['group'], other_student['github'], other_student['name'],
                        other_student['group']))
            # 2. does this student already have a github account?
            elif other_student['github'] != self.student['github']:
                # here we assume that other_student and student are the same person
                raise ValueError(
                    "GitHub account for student '{}' from group '{}' is '{}'. Can't set it to '{}'. Contact course staff if you want to update it.".format(
                        self.student['name'], self.student['group'], other_student['github'], self.student['github']))
            # 3. If not 1 & 2, then it must be a duplicate, so ignore it
            else:
                # return data_update
                is_new_student = False
        # TODO: join validity checks 1 & 2 above to be just a single check
        # ^ seems to be done!
        if is_new_student:
            student_position = self.find_student(dimension=dimension, searchby='name')
            github_column = self._find_github_column(dimension=dimension)
            values_count = len(self.data[self.student['group']][github_column])
            if values_count < student_position + 1:
                self.data[self.student['group']][github_column] = [
                    self.data[self.student['group']][github_column][i] if i < values_count else "" for i in
                    range(0, student_position + 1)
                ]
            self.data[self.student['group']][github_column][student_position] = self.student['github']
            data_update.append({
                'range': "{}!{}{}".format(self.student['group'], self.colnum_string(github_column, True), student_position + 1),
                # 'majorDimension': dimension,
                'values': [[self.student['github']]]
            })
            print("Pending write operation: {} @ {}".format(data_update[-1]['values'], data_update[-1]['range']))
        return data_update

    def set_student_lab_status(self, lab_id, value, dimension='COLUMNS', data_update=[]) -> list:
        """
        Set student's result for lab 'lab_id' to 'value'

        :param data: dict with sheet name as key and data as value
        :param student: dict with at least 'group' and one of 'name' or 'github' keys
        :param lab_id: integer lab identifier (starting from 1 onwards)
        :param value: string value to be set as student's lab_id result
        :param dimension: how the data is stored, see spreadsheet.values().batchGet
        :param data_update: a list of pending data updates prepared for
        spreadsheets.values.batchUpdate request
        :returns: a list of pending data update requests with appended
        request to update github account for the user in question
        :raises ValueError:
        """
        if dimension != 'COLUMNS':
            raise ValueError("Not implemented! Only 'COLUMNS' dimension value is supported at the moment.")
        student_position = self.find_student(dimension=dimension)
        lab_column = self.LAB_COLUMN_OFFSET + lab_id
        values_count = len(self.data[self.student['group']][lab_column])
        if values_count < student_position + 1:
            self.data[self.student['group']][lab_column] = [
                self.data[self.student['group']][lab_column][i] if i < values_count else "" for i in
                range(0, student_position + 1)
            ]
        # print(student)
        # print(lab_column, student_position, values_count, len(data[student['group']][lab_column]))
        # print(data[student['group']][lab_column])
        self.data[self.student['group']][lab_column][student_position] = value
        data_update.append({
            'range': "{}!{}{}".format(self.student['group'], self.colnum_string(lab_column, True), student_position + 1),
            # 'majorDimension': dimension,
            'values': [[value]]
        })
        print("Pending write operation: {} @ {}".format(data_update[-1]['values'], data_update[-1]['range']))
        return data_update

    def _find_github_column(self, dimension='COLUMNS'):
        """
        Find GitHub column id (zero-based)

        :param data: dict with sheet name as key and data as value
        :param student: dict with a 'group' key
        :param dimension: how the data is stored, see spreadsheet.values().batchGet
        :returns: zero-based column number of GitHub column
        :raises ValueError: if GitHub column is not found
        """
        github_column = None
        for i in range(0, len(self.data[self.student['group']])):
            if 'GitHub' in self.data[self.student['group']][i]:
                github_column = i
                break
        if github_column is None:
            raise ValueError(
                "Internal error! GitHub account column not found on sheet {}. Please, verify spreadsheet integrity!"
                                                                                        .format(self.student['group']))
        return github_column

    def find_student(self, student, dimension='COLUMNS', searchby='name'):
        """
        Find student in data from multiple sheets. A student is described by his/her
        group and either name or github account. If both student's name and
        github account are present, the value of searchby param is used to determine
        which one of them will be used. If student's name is missing, but github
        account is present, value of searchby is ignored.

        :param data: dict with sheet name as key and data as value
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
                position = self.data[student['group']][self.STUDENT_NAME_COLUMN].index(student['name'])
            except ValueError:
                raise ValueError(
                    "Student '{}' not found in group {}! Check spelling or contact course staff if you are not on the group list.".format(
                        student['name'], student['group']))
        elif 'github' in student:
            github_column = self._find_github_column(dimension)
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
                student['name'] = self.data[student['group']][self.STUDENT_NAME_COLUMN][position]
                student['position'] = position
                return student
        raise ValueError("Student with GitHub account {} not found in any of the groups!".format(github))

    def get_student_task_id(self, dimension='COLUMNS'):
        """
        Find stident's task id from google spreadsheet

        :param data: dict with sheet name as key and data as value
        :param student: dict with at least 'name' and 'group' keys
        :param dimension: how the data is stored, see spreadsheet.values().batchGet
        :returns: task id if student is found
        :raises ValueError: if either group or student are not found in data
        """
        TASK_ID_COLUMN = 0
        if dimension != 'COLUMNS':
            raise ValueError("Not implemented! Only 'COLUMNS' dimension value is supported at the moment.")
        student_position = self.find_student(dimension=dimension)
        task_id = self.data[self.student['group']][TASK_ID_COLUMN][student_position]
        return task_id

    def get_student_github(self, student, dimension='COLUMNS'):
        """
        Get student's GitHub account from google spreadsheet

        :param data: dict with sheet name as key and data as value
        :param student: dict with at least 'name' and 'group' keys
        :param dimension: how the data is stored, see spreadsheet.values().batchGet
        :returns: GitHub account name if student is found. None if student is found, but has no account
        :raises ValueError: if either group, student or GitHub column are not found in data
        """
        if dimension != 'COLUMNS':
            raise ValueError("Not implemented! Only 'COLUMNS' dimension value is supported at the moment.")
        student_position = self.find_student(student, dimension=dimension)
        github_column = self._find_github_column(dimension)
        student_github = None
        try:
            student_github = self.data[student['group']][github_column][student_position]
            if len(student_github.strip()) == 0:
                student_github = None
        except IndexError:
            student_github = None
        return student_github

    def get_student_lab_status(self, lab_id, dimension='COLUMNS'):
        """
        Get student's lab status from google spreadsheet

        :param data: dict with sheet name as key and data as value
        :param student: dict with at least 'name' and 'group' keys
        :param lab_id: integer lab identifier (starting from 1 onwards)
        :param dimension: how the data is stored, see spreadsheet.values().batchGet
        :returns: status of lab if student is found. None if student is found, but has no status for that lab
        :raises ValueError: if either group or student are not found in data
        """
        if dimension != 'COLUMNS':
            raise ValueError("Not implemented! Only 'COLUMNS' dimension value is supported at the moment.")
        student_position = self.find_student(dimension=dimension)
        student_lab_status = None
        try:
            lab_column = self.LAB_COLUMN_OFFSET + lab_id
            student_lab_status = self.data[self.student['group']][lab_column][student_position]
        except IndexError:
            student_lab_status = None
        if student_lab_status == "":
            student_lab_status = None
        return student_lab_status

    def get_lab_deadline(self, group, lab_id, dimension='COLUMNS'):
        """
        Get deadline for a lab

        :param data: dict with sheet name as key and data as value
        :param group: group the deadline to retrieve for
        :param lab_id: integer lab identifier (starting from 1 onwards)
        :param dimension: how the data is stored, see spreadsheet.values().batchGet
        :returns: deadline for a given lab
        """
        if dimension != 'COLUMNS':
            raise ValueError("Not implemented! Only 'COLUMNS' dimension value is supported at the moment.")
        try:
            lab_column = self.LAB_COLUMN_OFFSET + lab_id
            lab_deadline = self.data[group][lab_column][0]
        except IndexError:
            lab_deadline = None
        return lab_deadline


def main():
    StudentGoogleSheet.spreadsheet_connect()

if __name__ == '__main__':
    main()
