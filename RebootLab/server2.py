from http.server import BaseHTTPRequestHandler
from http.server import HTTPServer
from socket import gethostbyname, gethostname
from io import BytesIO

import os.path
import socket
import json
import subprocess
from datetime import datetime

api_key = "+<9AkQNWb8_"
ip_adress = gethostbyname(gethostname())
log_file = "/var/log/RebootLab.log"
env_file = ".env"
port = 9185


def run():
  httpd = HTTPServer((ip_adress, port), HttpGetHandler)
  
  try:
      print('Server is running, please, press Ctrl+C to stop\n')
      httpd.serve_forever()
  except KeyboardInterrupt:
      httpd.server_close()
      print('Errot: server cant be running\n')


class HttpGetHandler(BaseHTTPRequestHandler):

    def _set_headers(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()

    def do_GET(self):
        self._set_headers()
        self.wfile.write(b"")

    def do_POST(self):
        self._set_headers()
        content_len = int(self.headers['Content-Length'])
        post_body = str(self.rfile.read(content_len))
        print(str(self.headers)+post_body)
        #print(post_body)
        self.wfile.write(b"received post request:" + bytes(post_body, 'utf-8'))
        
        #service_restart('redis-server.service')

    def do_PUT(self):
        self.do_POST()


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
                    #response(service, action, status, code='500 Internal Server Error')
                    print(f"[ERROR]: Service restarting failed\n")
                else:
                    log_write("INFO", f"Status: {status}", f"Action: {action}", f"Service: {service}", f"PIDS: {(' '.join([str(f'{pidid}') for pidid in pids]))}")
                    #response(service, action, status)
                    print(f"[OK] Service restarting successful\n")
        else:
            status = "Inacive, restarting failed"
            log_write("ERROR", f"Status: {status}", f"Action: {action}", f"Service: {service}", f"PIDS: {(' '.join([str(f'{pidid}') for pidid in pids]))}")
            print(f"[ERROR] Restarting failed, service stoped\n")
            #response(service, action, status, code='500 Internal Server Error')
    else:
        print(f"Service inactive\n Starting...")
        sctl_start = bash_command(f"sudo systemctl start {service}", out=True)
        action = "Start"
    
        if ' ' not in sctl_start:
            status = "Active, starting successful"
            log_write("INFO", f"Status: {status}", f"Action: {action}", f"Service: {service}")
            #response(service, action, status)
            print(f"[OK] Service {service} started\n")
        else:
            status = "Dead, starting failed"
            error = sctl_start.replace('\n', ' ')
            log_write("ERROR", f"Status: {status}", f"Action: {action}", f"Service: {service}", error=f"Error: {error}")
            #response(service, action, status, code='500 Internal Server Error')
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
    #response(service, "status", status)
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
                #response(service, action, status)
                print(f"[ERROR]: Service stop failed\n")
        else:
            status = "Inactive, stop successful"
            log_write("INFO", f"Status: {status}", f"Action: {action}", f"Service: {service}", f"PIDS: {(' '.join([str(f'{pidid}') for pidid in pids]))}")
            print(f"[INFO] Service stoped\n")
            #response(service, action, status)
    else:
        status = "Service already stopped"
        action = "None"
        log_write("INFO", f"Status: {status}", f"Action: {action}", f"Service: {service}")
        print(f"[INFO] Service already stopped\n")
        #response(service, action, status)
    
    return action, status

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


def log_write(loglevel, *attrs, error=''):
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
