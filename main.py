from datetime import datetime
from fastapi import FastAPI, Response, Request, status as code
import json
from os.path import exists, isfile
from os import mkdir
from pydantic import BaseModel
from subprocess import Popen, STDOUT, PIPE

from settings import *


app = FastAPI()

class Request_Data(BaseModel):
    service_name: str
    action: str
    api_key: str


@app.post('/', status_code=code.HTTP_200_OK)
async def service(request_data: Request_Data, api_response: Response, api_request: Request):
    if api_request.client.host not in allowed_hosts:
        log_write('ERROR', message='Host not allowed')
        api_response.status_code = code.HTTP_403_FORBIDDEN
        
        return {'ok': False, 'message': 'Host not allowed'}
    
    login = check_auth(request_data.api_key)

    if login is None:
        log_write('ERROR', message='Invalid API key')
        api_response.status_code = code.HTTP_401_UNAUTHORIZED
        
        return {'ok': False, 'message': 'Invalid API key'}

    if request_data.service_name in services_list:
        service = services_list[request_data.service_name]
    else:
        log_write('ERROR', message='Unknown service name', login=login)
        api_response.status_code = code.HTTP_404_NOT_FOUND
        
        return {'ok': False, 'message': 'Unknown service name'}

    if not check_limit_of_requests(service):
        log_write('ERROR', message='Too many requests', login=login)
        api_response.status_code = code.HTTP_200_OK

        return {'ok': False, 'message': 'Too many requests'}

    api_response.status_code, json_response = do_action(login, service, request_data.action)

    return json_response


def check_auth(key):
    return api_logins.get(key)


def check_limit_of_requests(service):
    date_today = datetime.now().strftime('%d.%m.%Y')
    time_now = datetime.now().strftime('%X')
    req_count = 0
    log_file = create_log_file()

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

    return int(time_string[0]) * 3600 + int(time_string[1]) * 60 + int(time_string[2])


def bash_command(command, output=False):
    cmd = Popen(command, shell=True, stderr=STDOUT, stdout=PIPE)
    
    if output:
        return cmd.communicate(timeout=10)[0].decode('utf-8')

    return cmd


def create_log_file():
    date_today = datetime.now().strftime('%d.%m.%Y')
    current_log_file = f'{log_dir}/logfile_{date_today}.json'

    if not exists(log_dir):
        mkdir(log_dir)
    
    if not isfile(current_log_file):
        with open(current_log_file, 'x', encoding='utf-8') as logfile:
            logfile.write('[]')

    if isfile(current_log_file):
        return current_log_file
    
    return False


def log_write(loglevel, **log_items):
    log_file = create_log_file()

    if not log_file:
        print(f'Error: logfile not be created')
        return False
    
    log_json_data = json.load(open(log_file, 'r', encoding='utf-8'))
    log_string = dict(loglevel=loglevel.upper(), date=datetime.now().strftime('%d.%m.%Y'),
                      time=datetime.now().strftime('%X'), **log_items)
    log_json_data.append(log_string)
    json.dump(log_json_data, open(log_file, 'w', encoding='utf-8'), indent=2)


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

    return code.HTTP_200_OK, {'service': service, 'action': 'status', 'status': status}


def service_restart(login, service):
    status = systemctl_status(service, getstatus=True)

    if 'inactive' not in status:
        port = service_ports_list.get(service)
        kill(port)
        systemctl_restart(service)
        status = systemctl_status(service, getstatus=True, sleep=1)
    
        if 'inactive' not in status:
            log_write('INFO', message='Starting successful', login=login, action='kill, restart', service=service, status=status)
            return code.HTTP_200_OK, {'message': 'Restarting successful', 'service': service, 'action': 'kill, restart',
                                      'status': status}
        else:
            log_write('ERROR', message='Restarting failed, service stoped', login=login, action='kill, restart', service=service,
                      status=status)
            return code.HTTP_500_INTERNAL_SERVER_ERROR, {'message': 'Restarting failed, service stoped', 'service': service,
                                                         'action': 'kill, restart', 'status': status}
    else:
        error = systemctl_start(service, output=True)
        status = systemctl_status(service, getstatus=True, sleep=1)
    
        if 'inactive' not in status:
            log_write('INFO', message='Starting successful', login=login, action='start', service=service, status=status)
            return code.HTTP_200_OK, {'message': 'Starting successful', 'service': service, 'action': 'start', 'status': status}
        else:
            log_write('ERROR', message='Starting failed', login=login, action='start', service=service, status=status, error=error)
            return code.HTTP_500_INTERNAL_SERVER_ERROR, {'message': 'Starting failed', 'service': service, 'action': 'start',
                                                         'status': status}


def systemctl_status(service, output=False, getstatus=False, sleep=0):
    status_output = bash_command(f'sleep {sleep}; systemctl status {service}', output=True)
    
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


def systemctl_restart(service, output=False):
    start_output = bash_command(f'sudo systemctl restart {service}', output=output)

    if output:
        return start_output.replace('\n', ' ').strip()


def kill(port):
    bash_command(f'sudo kill -9 $(sudo lsof -ti tcp:{port})')
