from http.server import BaseHTTPRequestHandler
from http.server import HTTPServer
from socket import gethostbyname, gethostname

import os.path
import json
import subprocess
from datetime import datetime
from time import sleep


api_key = "+<9AkQNWb8_"
ip_adress = gethostbyname(gethostname())
log_file = "log.json"
env_file = ".env"
port = 9185


def run():
    httpd = HTTPServer((ip_adress, port), HttpHandler)
    
    try:
        print('Server is running, please, press Ctrl+C to stop\n')
        httpd.serve_forever()
    except KeyboardInterrupt:
        httpd.server_close()
        print('Server closed by KeyboardInterrupt\n')


class HttpHandler(BaseHTTPRequestHandler):

    def _send_response(self, code, json=None):
        self.send_response(code)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(bytes(str(json), 'utf-8'))

    def do_POST(self):
        content_len = int(self.headers['Content-Length'])
        post_body = str(self.rfile.read(content_len)).decode()
        print(post_body)

        json_data = json.load(post_body)
                
        if 'json' in self.headers['Content-Type']:
            #startjson = post_body.find('{"')
            #endjson = post_body.find('"}')
            #json_data = post_body[startjson:endjson+2]
            
            

            try:
                json_file = json.loads(json_data)
            except:
                json_file = None

            if json_file != None:
                if 'service_name' in json_file and 'action' in json_file and 'api_key' in json_file:
                    if json_file['api_key'] == api_key:
                        service = get_servname_from_dict(json_file['service_name'])

                        if service != -1:
                            if json_file['action'] == 'status':
                                code, json_response = service_status(service)
                            elif json_file['action'] == 'restart' or json_file['action'] == 'start':
                                code, json_response = service_restart(service)
                            elif json_file['action'] == 'stop' or json_file['action'] == 'kill':
                                code, json_response = service_kill(service)
                            else:
                                log_write("ERROR", "Wrong action")
                                print("[ERROR] Wrong action\n")

                            json_response = json.dumps(json_response)
                            self._send_response(code, json_response)
                        else:
                            log_write("ERROR", "Unknown service name")
                            self._send_response(404)
                            print("[ERROR] Unknown service name\n")
                    else:
                        log_write("ERROR", "Invalid API key")
                        self._send_response(401)
                        print("[ERROR] Invalid API key\n")
                else:
                    log_write("Error", "Invalid request")
                    self._send_response(400)
                    print("[Error] Invalid request\n")
            else:
                log_write("Error", "Invalid JSON")
                self._send_response(400)
                print("[Error] Invalid JSON\n")
        else:
            log_write("Error", "Missing JSON data")
            self._send_response(400)
            print("[Error] Missing JSON data\n")
        

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


def service_status(service, full=True):
    sctlstatus = bash_command(f"sudo systemctl status {service}",out=True)
    start = sctlstatus.find('Active: ')
    
    if full:
        end = sctlstatus.find(')', start)
        status = sctlstatus[start+8:end+1]
    else:
        end = sctlstatus.find('(', start)
        status = sctlstatus[start+8:end-1]
       
    code = 200

    log_write("INFO", f"Service: {service}", f"Status: {status}")
    print(f"{service} status: {status}\n")

    json_data = dict(serice=service, action='status', status=status)

    return code, json_data


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
                code = 200
                log_write("ERROR", f"Status: {status}", f"Action: {action}", f"Service: {service}", f"PIDS: {(' '.join([str(f'{pidid}') for pidid in pids]))}")
                print(f"[ERROR]: Service stop failed\n")
        else:
            status = "Inactive, stop successful"
            code = 200
            log_write("INFO", f"Status: {status}", f"Action: {action}", f"Service: {service}", f"PIDS: {(' '.join([str(f'{pidid}') for pidid in pids]))}")
            print(f"[INFO] Service stoped\n")
    else:
        status = "Service already stopped"
        action = "None"
        code = 200
        log_write("INFO", f"Status: {status}", f"Action: {action}", f"Service: {service}")
        print(f"[INFO] Service already stopped\n")

    json_data = dict(serice=service, action=action, status=status)
    
    return code, json_data


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


def log_write(loglevel, *items):
    try:
        logfile = open(log_file, 'x')
        logfile.close()
    except:
        pass
    
    log_entry = dict(loglevel=loglevel, data_time=datetime.now().strftime('%d.%m.%Y_%X'))
    log_data = json.load(open(log_file))
    log_data.append(log_entry)

    sleep(5)

    with open(log_file, 'w') as logfile:
        json.dump(log_data, logfile, indent=2)

    #for item in items:
    #    log_entry[item]

    #logfile.close()
    

def logwrite(loglevel, *attrs, error=''):
    logfile = open(log_file, 'a')
    logfile.write(f"[{datetime.now().strftime('%d.%m.%Y_%X')}][INFO]")
    #logfile.write("(" + ','.join([(f'"{head}={headers[head]}"') for head in headers]) + ')\n')
    
    if error != '':
        logfile.write(f"[{datetime.now().strftime('%d.%m.%Y_%X')}][ERROR]")
        logfile.write(f"({error})\n")
    
    logfile.write(f"[{datetime.now().strftime('%d.%m.%Y_%X')}][{loglevel}]")
    quote = '"'
    logfile.write(f"({','.join([(f'{quote}{attr}{quote}') for attr in attrs])});\n")

    logfile.close()

run()