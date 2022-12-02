from fastapi import FastAPI, Response, Header, status as code
from pydantic import BaseModel
import os.path
import json
import subprocess
from datetime import datetime


api_keys = dict(l2='+<9AkQNWb8_',
                other='123qweasd')
log_file = "log.json"
env_file = ".env"
port = 9185


app = FastAPI()


class Request(BaseModel):
    service_name: str
    action: str
    api_key: str


@app.post("/", status_code=code.HTTP_200_OK)
async def recieve_post(request: Request, response: Response):
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


def bash_command(command, out=False):
    cmd = subprocess.Popen(command, shell=True, stderr=subprocess.STDOUT, stdout=subprocess.PIPE)
    
    if out:
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
        log_string = dict(loglevel=loglevel.upper(), datetime=datetime.now().strftime('%d.%m.%Y_%X'))


        for key, value in log_items.items():
            log_string[f'{key}'] = value
        
        if logfile.tell() > 6:
            logfile.truncate(logfile.tell() - 2)
            logfile.write(',\n  ')
        elif logfile.tell() < 6:
            logfile.truncate(0)
            logfile.write('[\n  ')
        else:
            logfile.truncate(logfile.tell() - 2)
        
        logfile.write(json.dumps(log_string) + '\n]')
        print(','.join([(f'{key}={value}') for key, value in log_items.items()]))
    

def get_servname_from_env(service):
    if not os.path.isfile(env_file):
        return -1
    
    envfile = open(env_file, 'r')
    services_dict = envfile.readlines()

    services_name = -1

    for env_string in services_dict:
        if "#" in env_string:
            if service + " " in env_string:
                services_name = env_string[env_string.find(' ') + 1:env_string.find('#')].replace(' ', '')
                print(services_name)
        else:
            if service + " " in env_string:
                services_name = env_string[env_string.find(' ') + 1:].replace('\n', '')
    
    return services_name


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
            return service_status(login, service)
        case 'restart':
            return service_restart(login, service)
        case _:
            log_write('ERROR', message='Wrong action')
            return code.HTTP_404_NOT_FOUND, {'ok': False, 'message': 'Wrong action'}


def service_status(login, service):
    sctl_status = bash_command(f'sudo systemctl status {service}', out=True)
    status_start = sctl_status.find('Active: ') + 8
    status_end = sctl_status.find(')', status_start) + 1
    status = sctl_status[status_start:status_end]

    log_write("INFO", login=login, service=service, action='status', status=status)

    return code.HTTP_200_OK, dict(service=service, action='status', status=status)


def service_restart(login, service):
    sctl_status = bash_command(f'sudo systemctl status {service}', out=True)

    if 'Active: active' in sctl_status:
        pids = search_pids(sctl_status)
        
        for pid in pids:
            bash_command(f'sudo kill {pid}')
            print(f"PID {pid}: killing...")
        
        sctl_status = bash_command(f'sleep 1; sudo systemctl status {service}', out=True)
        newpids = search_pids(sctl_status)

        if 'Active: active' not in sctl_status:
            bash_command(f'sudo systemctl start {service}', out=False)
            sctl_status = bash_command(f'sleep 1; sudo systemctl status {service}', out=True)
            action = 'kill, start'
        else:
            action = 'kill'
        
        if 'Active: active' in sctl_status:
            status = 'Active, restarting successful'
            
            newpid_in_pids = False

            for newpid in newpids:
                if newpid in pids:
                    status = 'Active, restarting failed'
                    status_code = code.HTTP_500_INTERNAL_SERVER_ERROR
                    log_write('ERROR', login=login, action=action, service=service, status=status, pids=', '.join([str(f'{pidid}') for pidid in pids]))
                    pid_in_newpids = True
                    break

            if not newpid_in_pids:    
                status_code = code.HTTP_200_OK
                log_write('INFO', login=login, action=action, service=service, status=status, pids=', '.join([str(f'{pidid}') for pidid in pids]))
        else:
            status = 'Inacive, restarting failed, service stoped'
            status_code = code.HTTP_500_INTERNAL_SERVER_ERROR
            log_write('ERROR', login=login, action=action, service=service, status=status, pids=', '.join([str(f'{pidid}') for pidid in pids]))
    else:
        print(f'Service inactive\n Starting...')
        sctl_start = bash_command(f'sudo systemctl start {service}', out=True)
        action = 'start'
    
        if ' ' not in sctl_start:
            status = 'Active, starting successful'
            status_code = code.HTTP_200_OK
            log_write('INFO', login=login, action=action, service=service, status=status)
        else:
            status = 'Inactive, starting failed'
            status_code = code.HTTP_500_INTERNAL_SERVER_ERROR
            error = sctl_start.replace('\n', ' ')
            log_write('ERROR', login=login, action=action, service=service, status=status, error=error)
                
    response = dict(service=service, action=action, status=status)

    return status_code, response
