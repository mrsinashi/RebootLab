import os.path
import socket
import json
import subprocess
from datetime import datetime


api_key = "+<9AkQNWb8_"
ip_adress = socket.gethostbyname(socket.gethostname())
log_file = "/var/log/RebootLab.log"
env_file = ".env"
port = 9185


def init():
    sock = socket.socket()
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((ip_adress, port))
    sock.listen(5)

    if not os.path.isfile(log_file):
        if bash_command(f"sudo touch {log_file}"):
            print('Can\'t create logfile\n')
        else:
            print('Logfile created\n')
    
    print('Server is running, please, press Ctrl+C to stop\n')

    return sock


def bash_command(command, out=False):
    cmd = subprocess.Popen(command, shell=True, stderr=subprocess.STDOUT, stdout=subprocess.PIPE)
    
    if out:
        cmd = cmd.communicate(timeout=10)[0].decode('utf-8')

    return cmd

def get_servname_from_dict(service):
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
                services_name = env_string[env_string.find(" ") + 1:]
    
    return services_name


def response(service, action, status, code='200 OK'):
    json_data = dict(service=service, action=action, status=status)
    
    resp = (f"HTTP/1.1 {code}\r\n"
            "Content-Type: application/json\r\n"
            "Server: Analizator\r\n"
            "\r\n"
            f"{json.dumps(json_data)}"
            )

    conn.send(bytes(resp, encoding="utf-8"))


def search_pids(sctl):
    pids = []
    id_sym = 0

    while True:
        symbols = ["└─", "├─",]
        idpid = sctl.find(symbols[id_sym])

        if idpid != -1:
            pidend = sctl.find(" ", idpid+2, idpid+8)
            pids.append(sctl[idpid+2:pidend])
            sctl = sctl.replace(symbols[id_sym], " ")
            id_sym = 1
        else:
            return pids
            break
    

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
                    log_write("ERROR", f"Status: {status}", f"Action: {action}", f"Service: {service}", f"PIDS: {(' '.join([str(f'{pidid}') for pidid in pids]))}")
                    response(service, action, status, code='500 Internal Server Error')
                    print(f"[ERROR]: Service restarting failed\n")
                else:
                    log_write("INFO", f"Status: {status}", f"Action: {action}", f"Service: {service}", f"PIDS: {(' '.join([str(f'{pidid}') for pidid in pids]))}")
                    response(service, action, status)
                    print(f"[OK] Service restarting successful\n")
        else:
            status = "Inacive, restarting failed"
            log_write("ERROR", f"Status: {status}", f"Action: {action}", f"Service: {service}", f"PIDS: {(' '.join([str(f'{pidid}') for pidid in pids]))}")
            print(f"[ERROR] Restarting failed, service stoped\n")
            response(service, action, status, code='500 Internal Server Error')
    else:
        print(f"Service inactive\n Starting...")
        sctl_start = bash_command(f"sudo systemctl start {service}", out=True)
        action = "Start"
    
        if ' ' not in sctl_start:
            status = "Active, starting successful"
            log_write("INFO", f"Status: {status}", f"Action: {action}", f"Service: {service}")
            response(service, action, status)
            print(f"[OK] Service {service} started\n")
        else:
            status = "Dead, starting failed"
            error = sctl_start.replace('\n', ' ')
            log_write("ERROR", f"Status: {status}", f"Action: {action}", f"Service: {service}", error=f"Error: {error}")
            response(service, action, status, code='500 Internal Server Error')
            print(f"\n[ERROR] Service {service} not started\n")
    
    return action, status


def service_status(service, full=True):
    sctlstatus = bash_command(f"sudo systemctl status {service}",out=True)
    start = sctlstatus.find('Active: ')
    
    if full:
        end = sctlstatus.find(')', start)
        status = sctlstatus[start+8:end+1]
    else:
        end = sctlstatus.find('(', start)
        status = sctlstatus[start+8:end-1]
       
    log_write("INFO", f"Service: {service}", f"Status: {status}")
    response(service, "status", status)
    print(f"{service} status: {status}\n")

    return status


def service_kill(service):
    sctl_status = bash_command(f"sudo systemctl status {service}", out=True)
    
    if "Active: active" in sctl_status:
        pids = search_pids(sctl_status)
        bash_command(f"sudo systemctl stop {service}")
        sctl_status = bash_command(f"sleep 1; sudo systemctl status {service}", out=True)
        action = "Stop"

        if "Active: active" in sctl_status:
            action = "Stop, kill"

            for pid in pids:
                bash_command(f"sudo kill {pid}")
                print(f"PID {pid}: killing...")

            sctl_status = bash_command(f"sleep 1; sudo systemctl status {service}", out=True)
            
            if "Active: active" in sctl_status:
                status = "Active, stop failed"
                log_write("ERROR", f"Status: {status}", f"Action: {action}", f"Service: {service}", f"PIDS: {(' '.join([str(f'{pidid}') for pidid in pids]))}")
                response(service, action, status)
                print(f"[ERROR]: Service stop failed\n")
        else:
            status = "Inactive, stop successful"
            log_write("INFO", f"Status: {status}", f"Action: {action}", f"Service: {service}", f"PIDS: {(' '.join([str(f'{pidid}') for pidid in pids]))}")
            print(f"[INFO] Service stoped\n")
            response(service, action, status)
    else:
        status = "Service already stopped"
        action = "None"
        log_write("INFO", f"Status: {status}", f"Action: {action}", f"Service: {service}")
        print(f"[INFO] Service already stopped\n")
        response(service, action, status)
    
    return action, status


def parse_http(req):
    data = str(req).split(r"\r\n")
    fhirst_header = data[0]
    starthttp = fhirst_header.find('HTTP')
    headers['Protocol'] = fhirst_header[starthttp:]

    if 'POST' in data[0]:
        headers['Method'] = 'POST'
    elif 'GET' in data[0]:
        headers['Method'] = 'GET'
    elif 'PUT' in data[0]:
        headers['Method'] = 'PUT'
    else:
        headers['Method'] = '?'
    
    for head in data:
        for string in strings:
            if string in head:
                headers[string.replace(': ', '')] = head.replace(string, '')
    
    return str(req), headers


def log_write(loglevel, *attrs, error=''):
    logfile = open(log_file, 'a')
    logfile.write(f"[{datetime.now().strftime('%d.%m.%Y_%X')}][INFO]")
    logfile.write("(" + ','.join([(f'"{head}={headers[head]}"') for head in headers]) + ')\n')
    
    if error != '':
        logfile.write(f"[{datetime.now().strftime('%d.%m.%Y_%X')}][ERROR]")
        logfile.write(f"({error})\n")
    
    logfile.write(f"[{datetime.now().strftime('%d.%m.%Y_%X')}][{loglevel}]")
    quote = '"'
    logfile.write(f"({','.join([(f'{quote}{attr}{quote}') for attr in attrs])});\n")

    logfile.close()


strings = ['Host: ',
           'User-Agent: ',
           'Content-Type: ',
           ]

headers = dict()
sock = init()


while True:
    conn, addr = sock.accept()
    req = conn.recv(1024)

    try:
        req, headers = parse_http(req)

        if "POST" in headers['Method']:
            if 'json' in headers['Content-Type']:
                startjson = req.find('{"')
                endjson = req.find('"}')
                json_data = req[startjson:endjson+2]
                json_file = json.loads(json_data)

                if 'service_name' in json_file and 'action' in json_file and 'api_key' in json_file:
                    if json_file['api_key'] == api_key:
                        service = get_servname_from_dict(json_file['service_name'])

                        if service != -1:
                            if json_file['action'] == 'status':
                                service_status(service)
                            elif json_file['action'] == 'restart' or json_file['action'] == 'start':
                                service_restart(service)
                            elif json_file['action'] == 'stop' or json_file['action'] == 'kill':
                                service_kill(service)
                            else:
                                log_write("ERROR", "Wrong action")
                                response("None", "None", "Wrong action", code='400 Bad Request')
                                print("[ERROR] Wrong action\n")
                        else:
                            log_write("ERROR", "Unknown service name")
                            response("None", "None", "Unknown service name", code='404 NotFound')
                            print("[ERROR] Unknown service name\n")
                    else:
                        log_write("ERROR", "Invalid API key")
                        response("None", "None", "Invalid API key", code='401 Unauthorized')
                        print("[ERROR] Invalid API key\n")
                else:
                    log_write("Error", "Invalid request")
                    response("None", "None", "Invalid request", code='400 Bad Request')
                    print("[Error] Invalid request\n")
            else:
                log_write("Error", "Missing JSON data")
                response("None", "None", "Missing JSON data", code='400 Bad Request')
                print("[Error] Missing JSON data\n")
        else:
            log_write("Error", f"Wrong method {headers['Method']}")
            response("None", "None", "Wrong method", code='405 Method Not Allowed')
            print(f"[Error] Wrong method {headers['Method']}\n") 
    except Exception as exception:
        log_write("Error", exception)
        response("None", "None", "Error. Check the request", code='400 Bad Request')
        print(f"{exception}r\n")

    conn.close()
