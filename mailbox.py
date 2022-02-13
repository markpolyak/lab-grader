import logging
import sys
import imaplib
import smtplib
# import getpass
import email
# import email.header

# Import the email modules we'll need
from email import policy
from email.parser import BytesParser
from email.message import EmailMessage

import unicodedata

import datetime

# import html2text
from bs4 import BeautifulSoup

# import settings

# EMAIL_ACCOUNT = ""

# Use 'INBOX' to read inbox.  Note that whatever folder is specified,
# after successfully running this script all emails in that folder
# will be marked as read.
# EMAIL_FOLDER = "INBOX"

# def get_first_text_block(email_message_instance):
#     maintype = email_message_instance.get_content_maintype()
#     if maintype == 'multipart':
#         for part in email_message_instance.get_payload():
#             if part.get_content_maintype() == 'text':
#                 return part.get_payload()
#     elif maintype == 'text':
#         return email_message_instance.get_payload()


def get_imap_connection(config):
    """
    Establish an IMAP connection

    :param config: a course config
    :returns: connection instance
    """
    logger = logging.getLogger(__name__)
    connection = imaplib.IMAP4_SSL(
        # settings.mail_imap_server,
        # str(settings.mail_imap_port)
        config['auth']['email']['imap']['server'],
        str(config['auth']['email']['imap']['port'])
    )
    try:
        rv, data = connection.login(
            # settings.mail_login, settings.mail_password
            config['auth']['email']['login'],
            config['auth']['email']['password']
        )
    except imaplib.IMAP4.error:
        logger.exception("Login failed!!!")
        # print("LOGIN FAILED!!!")
        sys.exit(1)
    # print(rv, data)
    logger.info("IMAP login result: %s %s", rv, data)
    rv, mailboxes = connection.list()
    if rv == 'OK':
        logger.debug("Mailboxes: %s", mailboxes)
        # print("Mailboxes:")
        # print(mailboxes)
    return connection


def process_students(imap_conn, valid_subjects):
    """
    Do something with emails messages in the folder.
    For the sake of this example, print some headers.
    """
    logger = logging.getLogger(__name__)
    rv, data = imap_conn.select("INBOX")
    if rv != 'OK':
        # print("ERROR: Unable to open mailbox ", rv)
        logger.critical("ERROR: Unable to open mailbox %s", rv)

    # rv, data = M.search(None, "ALL")
    # rv, data = M.uid('search', None, "ALL")
    rv, data = imap_conn.uid('search', None, "(UNSEEN)")
    if rv != 'OK':
        # print("No messages found!")
        logger.info("No messages found!")
        return

    # list of students
    students = []

    for uid in data[0].split():
        # rv, data = M.fetch(num, '(RFC822)')
        rv, data = imap_conn.uid('fetch', uid, '(RFC822)')
        if rv != 'OK':
            # print("ERROR getting message {}".format(uid))
            logger.error("ERROR getting message %s", uid)
            return

        # see https://docs.python.org/3/library/email.examples.html
        # for an email processing example
        msg = BytesParser(policy=policy.default).parsebytes(data[0][1])
        # msg = email.message_from_bytes(data[0][1], policy=policy.default)
        # hdr = email.header.make_header(
        #     email.header.decode_header(msg['Subject']))
        # subject = str(hdr)
        subject = msg['subject'].strip() if msg['subject'] is not None else ''
        # print('Message {}: {}'.format(uid, subject))
        # print('Raw Date: {}'.format(msg['Date']))
        logger.debug('Message %s: %s', uid, subject)
        logger.debug('Raw Date: %s', msg['Date'])
        # if subject == 'Кафедра':
        if subject.lower() not in [s.lower() for s in valid_subjects]:
            mark_unread(imap_conn, uid)
            # print("Subject not matched. This email is ignored and left unread\n")
            logger.debug("Subject not matched. This email is ignored and left unread\n")
            continue
        # # Now convert to local date-time
        # date_tuple = email.utils.parsedate_tz(msg['Date'])
        # if date_tuple:
        #     local_date = datetime.datetime.fromtimestamp(
        #         email.utils.mktime_tz(date_tuple))
        #     print(
        #         "Local Date:",
        #         local_date.strftime("%a, %d %b %Y %H:%M:%S %z")
        #     )
        email_timestamp = email.utils.parsedate_to_datetime(msg['Date'])
        logger.debug('Local Date: %s', email_timestamp)
        # print("Local Date:", email_timestamp)
        # print(get_first_text_block(msg))
        # bodytext = msg.get_content()
        # print(bodytext)
        # If we want to print a preview of the message content,
        # we can extract whatever the least formatted payload is
        # and print the first three lines.  Of course, if the message
        # has no plain text part printing the first three lines of html
        # is probably useless, but this is just a conceptual example.
        simplest = msg.get_body(preferencelist=('plain', 'html'))
        simplest_text = ''.join(
            simplest.get_content().splitlines(keepends=True)
        )
        # print(simplest_text)
        # print(html2text.html2text(simplest_text))
        if True:
            soup = BeautifulSoup(simplest_text, features="lxml")
            # kill all script and style elements
            for script in soup(["script", "style"]):
                script.extract()    # rip it out
            # get text
            text = soup.get_text(separator='\n')
            # break into lines and remove leading and trailing space on each
            lines = (line.strip() for line in text.splitlines())
            # break multi-headlines into a line each
            chunks = (
                phrase.strip() for line in lines for phrase in line.split("  ")
            )
            # drop blank lines
            text_chunks = [chunk for chunk in chunks if chunk]
            text = '\n'.join(text_chunks)
            # print(text)
            if len(text_chunks) >= 3:
                # print("Group: {}".format(text_chunks[0]))
                # print("Name: {}".format(text_chunks[1]))
                # print("Repo name: {}".format(text_chunks[2]))
                logger.debug("Group: %s", text_chunks[0])
                logger.debug("Name: %s", text_chunks[1])
                logger.debug("Repo name: %s", text_chunks[2])
                # make uppercase and
                # swap all valid non-numeric characters to english
                group = (text_chunks[0]
                         .upper()
                         .replace('М', 'M')
                         .replace('В', 'V')
                         .replace('З', 'Z')
                         .replace('К', 'K'))
                # remove all invalid characters
                group = ''.join([c for c in group if c in '0123456789MVZK'])
                # normalize unicode string
                # e.g. substitute non-breaking space ('\xa0')
                # with normal space; see https://stackoverflow.com/a/34669482
                name = unicodedata.normalize("NFKC", text_chunks[1])
                students.append({
                    'group': "'{}'".format(group),
                    'raw_group': text_chunks[0],
                    'name': name,
                    'github': text_chunks[2].encode('ascii', 'ignore').decode("utf-8"),
                    'email': msg['from'],
                    'uid': uid,
                    'email_subject': subject,
                    'email_timestamp': email_timestamp
                })
            else:
                # print(
                logger.error(
                    "Error! Unable to parse email body. "
                    "There should be at least 3 lines of text in the email.")
        # print(msg.keys())
        # print("")
    return students


def mark_unread(imap_connection, uid):
    """
    mark an email as unread

    :param imap_connection: connection object
    :param uid: uid of an email
    """
    imap_connection.uid('STORE', uid, '-FLAGS', '(\\Seen)')


def mark_flagged(imap_connection, uid):
    """
    mark an email as flagged
    """
    imap_connection.uid('STORE', uid, '+FLAGS', '(\\Flagged)')


# M = imaplib.IMAP4_SSL(settings.mail_imap_server,
#     str(settings.mail_imap_port))
#
# try:
#     # rv, data = M.login(EMAIL_ACCOUNT, getpass.getpass())
#     rv, data = M.login(settings.mail_login, settings.mail_password)
# except imaplib.IMAP4.error:
#     print ("LOGIN FAILED!!! ")
#     sys.exit(1)
#
# print(rv, data)
#
# rv, mailboxes = M.list()
# if rv == 'OK':
#     print("Mailboxes:")
#     print(mailboxes)

# rv, data = M.select(EMAIL_FOLDER)
# if rv == 'OK':
#     print("Processing mailbox...\n")
#     students = process_mailbox(M)
#     print(students)
#     M.close()
# else:
#     print("ERROR: Unable to open mailbox ", rv)
#
#     #set a message as unseen (unread)
#     #conn.uid('STORE', uid, '-FLAGS', '(\Seen)')
#
# M.logout()


def send_email(toaddrs, subject, message, email_config):
    """
    send an email

    :param toaddrs: list of recepients
    :param subject: email subject
    :param message: email body text
    :param config: a course config
    """
    server = smtplib.SMTP_SSL(
        # settings.mail_smtp_server, settings.mail_smtp_port
        email_config['smtp']['server'],
        email_config['smtp']['port']
    )
    server.ehlo()
    server.login(
        # settings.mail_login, settings.mail_password
        email_config['login'],
        email_config['password']
    )
    # server.sendmail(
    #     'k43guap@ya.ru', 'k43guap@ya.ru',
    #     'From: k43guap@ya.ru\nTo:k43guap@ya.ru\n'
    #     'Subject: test\n\nHello, world!')
    msg = EmailMessage()
    msg['From'] = email_config['return-address']
    msg['To'] = ','.join(toaddrs)
    msg['Subject'] = subject
    msg.set_content(message)
    # server.send_message(msg)
    # server.send_message(msg,
    #     from_addr=settings.mail_return_address, to_addrs=toaddrs)
    server.send_message(
        msg,
        from_addr=msg['from'],
        to_addrs=[a.addr_spec for a in msg['to'].addresses]
    )
    server.quit()


def main():
    # connection = get_imap_connection()
    # rv, data = connection.select("INBOX")
    # if rv == 'OK':
    #     print("Processing mailbox...\n")
    #     students = process_mailbox(connection)
    #     print(students)
    #     #
    #     gs = google_sheets.get_spreadsheet_instance()
    #     sheets = google_sheets.get_sheet_names(gs)
    #     print(sheets)
    #     sheets = ["'{}'".format(s) for s in sheets]
    #     data = google_sheets.get_multiple_sheets_data(gs, sheets)
    #     #
    #     data_update = []
    #     #
    #     for student in students:
    #         try:
    #             data_update = google_sheets.set_student_github(
    #                 data, student, data_update=data_update)
    #         except Exception as e:
    #             print("Unable to process student's '{}' request: {}".format(
    #                 student['name'], student))
    #             print(e)
    #             # set a message as unseen (unread)
    #             connection.uid('STORE', student['uid'], '-FLAGS', '(\Seen)')
    #     print(data_update)
    #     google_sheets.batch_update(gs, data_update)
    #
    #     connection.close()
    # else:
    #     print("ERROR: Unable to open mailbox ", rv)
    # connection.logout()
    None


if __name__ == '__main__':
    main()
