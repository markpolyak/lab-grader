import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry


def requests_retry_session(
        retries=3,
        backoff_factor=0.3,
        status_forcelist=(500, 502, 504),
        session=None):
    """
    Build a retry session for requests
    """
    session = session or requests.Session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session


def get_task_id(log):
    task_id_str = "TASKID is"
    i = log.find(task_id_str)
    # skip all occurences that start with a comma, 
    # e.g. from source code like `echo "TASKID is ..."`,
    # which is echoed to the log before being executed
    while i > 0 and (log[i - 1] == '"' or log[i - 1] == "'"):
        i = log.find(task_id_str, i + 1)
    if i < 0:
        return None
    i += len(task_id_str) + 1
    try:
        task_id = int(log[i:i + 2].strip())
    except ValueError as e:
        print(e)
        task_id = -1
    return task_id


def get_grade_reduction_coefficient(log):
    """
    get grade reduction coefficient by provided build log

    :param log: build log
    :return: grade reduction coefficient as str or None
    """
    reduction_str = "Grading reduced by"
    i = log.find(reduction_str)
    # skip all occurences that start with a comma, 
    # e.g. from source code like `echo "Grading reduced by ..."`,
    # which is echoed to the log before being executed
    while i > 0 and (log[i - 1] == '"' or log[i - 1] == "'"):
        i = log.find(reduction_str, i + 1)
    if i < 0:
        return None
    # print(log)
    # print(i)
    i += len(reduction_str) + 1
    reduction_percent = int(log[i:log.find("%", i)].strip())
    if reduction_percent == 0:
        return None
    else:
        # 0.01 * (100 - REDUCTION_PERCENT) = REDUCTION_COEFFICIENT in decimal form
        # return 0.01 * (100 - reduction_percent) # pure float coefficient
        # for current case, where percents could be in range [1; 100], using of 'g' format is OK
        return '{0:g}'.format(0.01 * (100 - reduction_percent))
