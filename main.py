from fastapi import FastAPI, Response, status as code
from pydantic import BaseModel
import os.path
import json
import subprocess
from datetime import datetime


api_keys = dict(l2='+<9AkQNWb8_')
log_file = "log.json"
env_file = ".env"
port = 9185


app = FastAPI()


class Request(BaseModel):
    service_name: str
    action: str
    api_key: str


@app.post("/", status_code=code.HTTP_200_OK)
async def service(request: Request, response: Response):
    login = auth_check(request.api_key)

    if login == -1:
        log_write('ERROR', message='Invalid API key')
        response.status_code = code.HTTP_401_UNAUTHORIZED
        
        return {'ok': False, 'message': 'Invalid API key'}

    service = get_servname_from_env(request.service_name)

    if service == -1:
        log_write('ERROR', login=login, message='Unknown service name')
        response.status_code = code.HTTP_404_NOT_FOUND
        
        return {'ok': False, 'message': 'Unknown service name'}

    response.status_code, json_response = do_action(login, service, request.action)

    return json_response


def auth_check(api_key):
    for login, apikey in api_keys.items():
        if apikey == api_key:
            return login
    
    return -1


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
        log_string = dict(loglevel=loglevel.upper(), datetime=datetime.now().strftime('%d.%m.%Y_%X'), **log_items)
        
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
    

def get_servname_from_env(service):
    if not os.path.isfile(env_file):
        return -1
    
    envfile = open(env_file, 'r')
    services_dict = envfile.readlines()

    service_name = -1

    for env_string in services_dict:
        if service + "=" in env_string:
            service_name = env_string[env_string.find('=') + 1:env_string.find('#')].strip(' #\n')
            print(service_name)
    
    return service_name


def search_pids(sctl):
    pids = []
    id_sym = 0

    while True:
        symbols = ['└─', '├─']
        pid_start = sctl.find(symbols[id_sym])

        if pid_start == -1:
            return pids
        
        pid_start = pid_start + 2

        pid_end = sctl.find(' ', pid_start, pid_start+6)
        pids.append(sctl[pid_start:pid_end])
        sctl = sctl.replace(symbols[id_sym], '__')
        id_sym = 1


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
        pids = search_pids(status_output)
        kill(pids)
        
        status_output, status = systemctl_status(service, output=True, getstatus=True, sleep=1)
        
        if 'inactive' in status:
            error = systemctl_start(service, output=True)
            status_output, status = systemctl_status(service, output=True, getstatus=True, sleep=1)
            action = 'kill, start'
        else:
            action = 'kill'
        
        if 'inactive' not in status:
            newpids = search_pids(status_output)
            failed_pids = list(set(pids) & set(newpids))
            
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
        print(f'Service inactive. Starting...')
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
        bash_command(f'sudo kill {pid}')
        print(f"PID {pid}: killing...")
