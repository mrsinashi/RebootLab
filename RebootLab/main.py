from fastapi import FastAPI, Response, status as code
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import socket
import json
import subprocess
from datetime import datetime


api_key = "+<9AkQNWb8_"
log_file = "log.json"
env_file = ".env"
port = 9185


class Request(BaseModel):
    service_name: str
    action: str
    api_key: str


app = FastAPI()


@app.post("/", status_code=code.HTTP_200_OK)
async def recieve_post(request: Request, response: Response):
  
    if request.api_key != api_key:
        log_write("ERROR", message='Invalid API key')
        print("[ERROR] Invalid API key\n")
        response.status_code = code.HTTP_401_UNAUTHORIZED
        
        return {'ok': False, 'message': 'Invalid API key'}

    service = get_servname_from_env(request.service_name)

    if service == -1:
        log_write("eroRr", message='Unknown service name')
        print("[ERROR] Unknown service name\n")
        response.status_code = code.HTTP_404_NOT_FOUND
        
        return {'ok': False, 'message': 'Unknown service name'}

    response.status_code, json_response = do_action(service, request.action)

    return json_response


def bash_command(command, out=False):
    cmd = subprocess.Popen(command, shell=True, stderr=subprocess.STDOUT, stdout=subprocess.PIPE)
    
    if out:
        return cmd.communicate(timeout=10)[0].decode('utf-8')

    return cmd


def log_write(loglevel, **log_items):
    with open(log_file, 'a+', encoding='utf-8') as logfile:
        logfile.truncate(logfile.tell() - 2)
        
        log_string = dict(loglevel=loglevel.upper(), datetime=datetime.now().strftime('%d.%m.%Y_%X'))
        
        for key, value in log_items.items():
            log_string[f'{key}'] = value
        
        logfile.write(",\n  " + json.dumps(log_string) + "\n]")
    

def get_servname_from_env(service):
    envfile = open(env_file, 'r')
    services_dict = envfile.readlines()

    services_name = -1

    for env_string in services_dict:
        if "#" in env_string:
            if service + " " in env_string:
                services_name = env_string[env_string.find(" ") + 1:env_string.find("#")].replace(' ', '')
                print(services_name)
        else:
            if service + " " in env_string:
                services_name = env_string[env_string.find(" ") + 1:].replace('\n', '')
    
    return services_name


def search_pids(sctl):
    pids = []
    id_sym = 0

    while True:
        symbols = ["└─", "├─",]
        idpid = sctl.find(symbols[id_sym])

        if idpid == -1:
            return pids

        pidend = sctl.find(" ", idpid+2, idpid+8)
        pids.append(sctl[idpid+2:pidend])
        sctl = sctl.replace(symbols[id_sym], " ")
        id_sym = 1


def do_action(service, action):
    match action:
        case 'status':
            return service_status(service)
        case 'restart' | 'start':
            return service_restart(service)
        case 'stop' | 'kill':
            return service_stop(service)
        case _:
            #log_write("ERROR", "Wrong action")
            print("[ERROR] Wrong action\n")
            return None


def service_status(service):
    sctlstatus = bash_command(f"sudo systemctl status {service}", out=True)
    start = sctlstatus.find('Active: ')
    end = sctlstatus.find(')', start)
    status = sctlstatus[start+8:end+1]

    log_write("INFO", dict(serice=service, action='status', status=status))
    print(f"{service} status: {status}\n")

    return code.HTTP_200_OK, dict(serice=service, action='status', status=status)


def service_restart(service):
    sctl_status = bash_command(f"sudo systemctl status {service}", out=True)

    if "Active: active" in sctl_status:
        pids = search_pids(sctl_status)
        
        for pid in pids:
            bash_command(f"sudo kill {pid}")
            print(f"PID {pid}: killing...")
        
        sctl_status = bash_command(f"sleep 1; sudo systemctl status {service}", out=True)
        newpids = search_pids(sctl_status)

        if "Active: active" not in sctl_status:
            bash_command(f"sudo systemctl start {service}", out=False)
            sctl_status = bash_command(f"sleep 1; sudo systemctl status {service}", out=True)
            action = "Kill, start"
        else:
            action = "Kill"
        
        if "Active: active" in sctl_status:
            status = "Active, restarting successful"
            
            for items in newpids:
                if pid in newpids:
                    status = "Active, restarting failed"
                    code = 500
                    log_write("ERROR", f"Status: {status}", f"Action: {action}", f"Service: {service}", f"PIDS: {(' '.join([str(f'{pidid}') for pidid in pids]))}")
                    print(f"[ERROR]: Service restarting failed\n")
                else:
                    code = 200
                    log_write("INFO", f"Status: {status}", f"Action: {action}", f"Service: {service}", f"PIDS: {(' '.join([str(f'{pidid}') for pidid in pids]))}")
                    print(f"[OK] Service restarting successful\n")
        else:
            status = "Inacive, restarting failed"
            code=500
            log_write("ERROR", f"Status: {status}", f"Action: {action}", f"Service: {service}", f"PIDS: {(' '.join([str(f'{pidid}') for pidid in pids]))}")
            print(f"[ERROR] Restarting failed, service stoped\n")
    else:
        print(f"Service inactive\n Starting...")
        sctl_start = bash_command(f"sudo systemctl start {service}", out=True)
        action = "Start"
    
        if ' ' not in sctl_start:
            status = "Active, starting successful"
            code = 200
            log_write("INFO", f"Status: {status}", f"Action: {action}", f"Service: {service}")
            print(f"[OK] Service {service} started\n")
        else:
            status = "Dead, starting failed"
            code = 500
            error = sctl_start.replace('\n', ' ')
            log_write("ERROR", f"Status: {status}", f"Action: {action}", f"Service: {service}", error=f"Error: {error}")
            print(f"\n[ERROR] Service {service} not started\n")
    
    json_data = dict(serice=service, action=action, status=status)

    return code, json_data


def service_stop():
    pass
