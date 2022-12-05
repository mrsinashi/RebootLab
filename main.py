from fastapi import FastAPI, Response, status as code
from pydantic import BaseModel
import os.path
import json
import subprocess
from datetime import datetime

from settings import *


app = FastAPI()


class Request(BaseModel):
    service_name: str
    action: str
    api_key: str


@app.post("/", status_code=code.HTTP_200_OK)
async def service(request: Request, response: Response):
    login = check_auth(request.api_key)

    if login == False:
        log_write('ERROR', message='Invalid API key')
        response.status_code = code.HTTP_401_UNAUTHORIZED
        
        return {'ok': False, 'message': 'Invalid API key'}

    if request.service_name in services_list:
        service = services_list[request.service_name]

    if service == -1:
        log_write('ERROR', message='Unknown service name', login=login)
        response.status_code = code.HTTP_404_NOT_FOUND
        
        return {'ok': False, 'message': 'Unknown service name'}

    if not check_freq_of_requests(service):
        log_write('ERROR', message='Too many requests', login=login)
        response.status_code = code.HTTP_200_OK

        return {'ok': False, 'message': 'Too many requests'}

    response.status_code, json_response = do_action(login, service, request.action)

    return json_response


def check_auth(api_key):
    for login, apikey in api_keys.items():
        if apikey == api_key:
            return login
    
    return False


def check_freq_of_requests(service):
    date_today = datetime.now().strftime('%d.%m.%Y')
    time_now = datetime.now().strftime('%X')
    req_count = 0

    with open(log_file, 'r') as logfile:
        log_json_data = json.loads(logfile.read())
        
        for log_string in log_json_data:
            if 'action' in log_string and 'service' in log_string:
                if (log_string['date'] == date_today
                and log_string['action'] != 'status'
                and log_string['service'] == service
                and time_str_to_int(log_string['time']) > time_str_to_int(time_now) - min_time_for_requests * 60):
                    req_count += 1

    if req_count < max_requests_in_time:
        return True
            
    return False
    

def time_str_to_int(time_string):
    time_string = time_string.split(':')

    return int(time_string[0])*3600 + int(time_string[1])*60 + int(time_string[2])


def bash_command(command, output=False):
    cmd = subprocess.Popen(command, shell=True, stderr=subprocess.STDOUT, stdout=subprocess.PIPE)
    
    if output:
        return cmd.communicate(timeout=10)[0].decode('utf-8')

    return cmd


def log_create():
    if os.path.isfile(log_file):
        return
    else:   
        logfile = open(log_file, 'x', encoding='utf-8')
        logfile.write("[\n  \n]")
        logfile.close()


def log_write(loglevel, **log_items):
    log_create()

    with open(log_file, 'a+', encoding='utf-8') as logfile:
        log_string = dict(loglevel=loglevel.upper(), date=datetime.now().strftime('%d.%m.%Y'), time=datetime.now().strftime('%X'), **log_items)
        
        if logfile.tell() > 6:
            logfile.truncate(logfile.tell() - 2)
            logfile.write(',\n  ')
        elif logfile.tell() < 6:
            logfile.truncate(0)
            logfile.write('[\n  ')
        else:
            logfile.truncate(logfile.tell() - 2)
        
        logfile.write(json.dumps(log_string) + '\n]')
        print(log_items)


def parse_pids(status_output):
    pids = []    
    cycles = 0

    if "CGroup: " not in status_output:
        pid_start = status_output.find("Process: ") + 9
        pid_end = status_output.find(' ', pid_start, pid_start+6)
        pids.append(status_output[pid_start:pid_end])
        return pids

    while True:
        cycles += 1
        
        if cycles > 100:
            return sorted(pids)

        symbols = ['├─', '└─']
        id_sym = 0
        pid_start = status_output.find(symbols[id_sym])

        if pid_start == -1:
            id_sym = 1
            pid_start = status_output.find(symbols[id_sym])
            
            if pid_start == -1:
                    return sorted(pids)

        pid_start += 2

        if status_output[pid_start:pid_start+2].isnumeric():
            pid_end = status_output.find(' ', pid_start, pid_start+6)
            pids.append(status_output[pid_start:pid_end])
            status_output = status_output.replace(symbols[id_sym], '__', 1)
            id_sym = 1
        else:
            status_output = status_output.replace(symbols[id_sym], '__', 1)


def do_action(login, service, action):
    match action:
        case 'status':
            return service_status(service)
        case 'restart':
            return service_restart(login, service)
        case _:
            log_write('ERROR', message='Wrong action', login=login)
            return code.HTTP_404_NOT_FOUND, {'ok': False, 'message': 'Wrong action'}


def service_status(service):
    status = systemctl_status(service, getstatus=True)

    return code.HTTP_200_OK, dict(service=service, action='status', status=status)


def service_restart(login, service):
    status_output, status = systemctl_status(service, output=True, getstatus=True)

    if 'inactive' not in status:
        pids = parse_pids(status_output)
        kill(pids)
        
        status_output, status = systemctl_status(service, output=True, getstatus=True, sleep=1)
        
        if 'inactive' in status:
            error = systemctl_start(service, output=True)
            status_output, status = systemctl_status(service, output=True, getstatus=True, sleep=1)
            action = 'kill, start'
        else:
            action = 'kill'
        
        if 'inactive' not in status:
            newpids = parse_pids(status_output)
            failed_pids = sorted(list(set(pids) & set(newpids)))

            if failed_pids == []:
                message = 'Restarting successful'
                status_code = code.HTTP_200_OK
                log_write('INFO', message=message, login=login, action=action, service=service, status=status, pids=pids)
            else:
                message = 'Restarting failed'
                status_code = code.HTTP_500_INTERNAL_SERVER_ERROR
                log_write('ERROR', message=message, login=login, action=action, service=service, status=status, pids=pids, failed_pids=failed_pids)
        else:
            message = 'Restarting failed, service stoped'
            status_code = code.HTTP_500_INTERNAL_SERVER_ERROR
            log_write('ERROR', message=message, login=login, action=action, service=service, status=status, pids=pids, error=error)
    else:
        error = systemctl_start(service, output=True)
        status_output, status = systemctl_status(service, output=True, getstatus=True, sleep=1)
        action = 'start'
    
        if 'inactive' not in status:
            message = 'Starting successful'
            status_code = code.HTTP_200_OK
            log_write('INFO', message=message, login=login, action=action, service=service, status=status)
        else:
            message = 'Starting failed'
            status_code = code.HTTP_500_INTERNAL_SERVER_ERROR
            log_write('ERROR', message=message, login=login, action=action, service=service, status=status, error=error)

    return status_code, dict(message=message, service=service, action=action, status=status)


def systemctl_status(service, output=False, getstatus=False, sleep=0):
    status_output = bash_command(f'sleep {sleep}; sudo systemctl status {service}', output=True)
    
    output_data = []

    if output:
        output_data.append(status_output)

    if getstatus:
        status_start = status_output.find('Active: ') + 8
        status_end = status_output.find(')', status_start) + 1
        status = status_output[status_start:status_end]
        output_data.append(status)
    
    return output_data


def systemctl_start(service, output=False):
    start_output = bash_command(f'sudo systemctl start {service}', output=output)

    if output:
        return start_output.replace('\n', ' ').strip()


def kill(pids):
    for pid in pids:
        bash_command(f'sudo kill -9 {pid}')
        print(f"PID {pid}: killing...")
