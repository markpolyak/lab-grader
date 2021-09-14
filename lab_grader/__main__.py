import argparse
import datetime
import logging
import os
import sys
from lab_grader import load_config, PathConfig
from lab_grader.core import Grader
from lab_grader.server import run_grader_server
import lab_grader.utils.mailbox as mailbox
import lab_grader.utils.google_sheets as google_sheets


# setup logging
def setup_logging(default_level=logging.INFO):
    if not sys.warnoptions:
        # Route warnings through python logging
        logging.captureWarnings(True)

    path_config = PathConfig()

    if os.path.exists(path_config.logger_config):
        config = load_config(path_to_yaml=path_config.logger_config)
        logging.config.dictConfig(config)
    else:
        logging.basicConfig(level=default_level)

    # set logging level for the root logger
    logging.getLogger().setLevel(default_level)


def _parse_args():
    """
    Internal function intended to parse command line arguments
    """
    parser = argparse.ArgumentParser(
        description="Process student updates from email and GitHub")

    path_config = PathConfig()

    parser.add_argument('-a', '--auth', dest='authentication_config', action='store',
                        default=path_config.auth_config,
                        help="authentication config file")

    parser.add_argument('--logging-config', dest='logging_config', action='store',
                        default=path_config.logger_config,
                        help='set logging config file')

    subparsers = parser.add_subparsers(title='mode', dest='mode', required=True,
                                       help="package running mode: server or task")
    # server mode
    server_parser = subparsers.add_parser('server')
    server_parser.add_argument('--listen', dest='instance', required=True,
                               help="host:port")

    # single task mode
    task_pasrser = subparsers.add_parser('task')

    # arguments of task mode
    task_pasrser.add_argument('-c', '--course-config', dest='course_config', action='store',
                              required=True,
                              help="course config file")

    task_pasrser.add_argument('-u', '--update', dest='update_action',
                              action='store', default=['all'],
                              choices=['all', 'email', 'labs', 'appveyor', 'moss'],
                              nargs='+',
                              help="action to be taken: "
                                   "perform ALL updates, read EMAILs only, check LABs only, "
                                   "add new APPVEYOR projects only, run MOSS plagiarism check;\n"
                                   "use a combination of flags, e.g. 'email labs' to read emails "
                                   "and check labs, without doing other updates")

    task_pasrser.add_argument('-l', '--labs', dest='labs',
                              action='store', nargs='+', default='all',
                              help="choose labs to be processed, default is all")

    # parser.add_argument(
    #     '--plagiarism', '--moss' dest='moss',
    #     action='store_true',
    #     help="check for plagiarism",
    # )
    task_pasrser.add_argument('--dry-run', dest='dry_run',
                              action='store_true',
                              help="do not update any real data, do not send any emails "
                                   "or save any results, just print to console")
    # parser.add_argument(
    #     '--ignore-email', dest='ignore_email',
    #     action='store_true',
    #     help="do not check for new emails",
    # )

    task_pasrser.add_argument('-v', '--verbose', dest='verbosity',
                              action='count', default=0,
                              help="verbose output (repeat for increased verbosity)")
    return parser.parse_args()


if __name__ == '__main__':
    # parse command line parameters
    params = _parse_args()

    if params.mode == 'server':
        run_grader_server(instance=params.instance)
    elif params.mode == 'task':
        # Python log levels go from 10 (DEBUG) to 50 (CRITICAL),
        # our verbosity argument goes from 0 to 2 (-vv).
        # We never want to suppress error and critical messages,
        # and default to use 30 (WARNING). Hence:
        base_loglevel = getattr(logging, 'WARNING')
        params.verbosity = min(params.verbosity, 2)
        loglevel = base_loglevel - (params.verbosity * 10)
        setup_logging(default_level=loglevel)
        logger = logging.getLogger(__name__)
        print(params.verbosity)

        grader = Grader(course_config=params.course_config, dry_run=params.dry_run, logs_vv=False)

        # check arguments
        if params.labs == 'all' or params.labs == '*':
            grader.course_config['labs'].keys()
        logger.info(params)
        # perform action
        if "moss" not in params.update_action:
            # initialization
            data_update = []
            # connect to Google Sheets API
            spreadsheet = google_sheets.GoogleSheet(grader.get_config())
            # # load data from Google Sheets
            # sheets = spreadsheet.get_sheet_names(gs, config)
            # # print(sheets)
            # sheets = ["'{}'".format(s) for s in sheets]
            # data = google_sheets.get_multiple_sheets_data(gs, sheets, config)
            # check email
            if "all" in params.update_action or "email" in params.update_action:
                # connect to IMAP
                imap_conn = mailbox.get_imap_connection(grader.get_config())
                # process INBOX and update spreadsheet
                data_update = grader.update_students(imap_conn, spreadsheet)

            # check labs
            if "all" in params.update_action or "labs" in params.update_action:
                for lab_id in params.labs:
                    grader.check_lab(lab_id, spreadsheet.sheets[:-1], spreadsheet)

            # update Google SpreadSheet
            if len(data_update) > 0:
                info_sheet = grader.get_config()['course']['google']['info-sheet']
                data_update.append({
                    'range': f"'{info_sheet}'!B1",
                    # 'majorDimension': dimension,
                    'values': [[datetime.datetime.now().isoformat()]]
                })
                logger.info("Data update: %s", data_update)
                # print(data_update)
                if not params.dry_run:
                    updated_cells = spreadsheet.batch_update()
                    if updated_cells != len(data_update):
                        raise ValueError(
                            f"Number of updated cells ({updated_cells}) differs "
                            "from expected ({len(data_update)})! Check the data "
                            "manually. Data update: {data_update}")
            try:
                imap_conn.close()
                imap_conn.logout()
            except Exception:
                pass
        elif "moss" in params.update_action:
            # check labs
            for lab_id in params.labs:
                grader.check_plagiarism(lab_id, "lab{}".format(lab_id))
    else:
        raise NotImplementedError

