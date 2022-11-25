import socket
import json
import subprocess
from time import sleep
from datetime import datetime
from collections import deque

api_key = "+<9AkQNWb8_"
ip_adress = "192.168.50.253"
log_path = "/var/log/RebootLab.log"
env_path = ".env"
port = 9185


def parse_serv_dict(service):
    envfile = open(env_path, 'r')
    services_dict = envfile.readlines()

    i = 0

    for srvdct in services_dict:
        services_dict[i] = srvdct.replace('\n', '').split(' ')
        i = i + 1

    services_dict = dict(services_dict)
    
    return services_dict[service]


sock = socket.socket()
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind((ip_adress, port))
sock.listen(5)
print('Server is running, please, press ctrl+c to stop\n')


def search_pids(systemctl):
    i = 0
    pids = []
    idpid = 0

    while True:
        symb = ["└─", "├─",]
        idpid = systemctl.find(symb[i])

        if idpid != -1:
            pidend = systemctl.find(" ", idpid+2, idpid+8)
            pids.append(systemctl[idpid+2:pidend])
            systemctl = systemctl.replace(symb[i], " ")
            i = 1
        else:
            return pids
            break
    

def restart_service(restartserv, apikey):
    if apikey == api_key:
        command = f"sudo systemctl status {restartserv}"
        systemctl = subprocess.Popen([command], shell=True, stdout=subprocess.PIPE)
        systemctl = systemctl.communicate(timeout=10)[0].decode('utf-8')

        if "Active: active" in systemctl:
            pids = search_pids(systemctl)
            
            for pid in pids:
                print(f"PID {pid}: killing...")
                subprocess.Popen([f"sudo kill {pid}"], shell=True, stdout=subprocess.PIPE)

            systemctl = subprocess.Popen([f"sleep 1; {command}"], shell=True, stdout=subprocess.PIPE)
            systemctl = systemctl.communicate(timeout=10)[0].decode('utf-8')

            pids2 = search_pids(systemctl)

            if "Active: active" not in systemctl:
                systemctl = subprocess.Popen(f"sudo systemctl start {restartserv}", shell=True, stderr=subprocess.STDOUT, stdout=subprocess.PIPE)
                systemctl = subprocess.Popen(f"sleep 1; {command}", shell=True, stdout=subprocess.PIPE)
                
                systemctl = systemctl.communicate(timeout=10)[0].decode('utf-8')
            if "Active: active" in systemctl:
                for pid2 in pids2:
                    if pid in pids2:
                        log_write("ERROR", "Service restarting failed", f"Service: {restartserv}", f"PIDS: {(' '.join([str(f'{pidid}') for pidid in pids]))}")
                        print(f"[ERROR]: Service restarting failed\n")
                        conn.send(b"[ERROR] Service restarting failed")
                    else:
                        log_write("INFO", "Service restarting succes", f"Service: {restartserv}", f"PIDS: {(' '.join([str(f'{pidid}') for pidid in pids]))}")
                        print(f"[OK] Service restarting succes\n")
                        conn.send(b"[OK] Service restarting succes")
            else:
                log_write("ERROR", "Restarting failed, service stoped", f"Service: {restartserv}", f"PIDS: {(' '.join([str(f'{pidid}') for pidid in pids]))}")
                print(f"[ERROR] Restarting failed, service stoped\n")
                conn.send(b"[ERROR] Restarting failed, service stoped")
        else:
            print(f"Service not running\n Starting...")
            systemctl = subprocess.Popen(f"sudo systemctl start {restartserv}", shell=True, stderr=subprocess.STDOUT, stdout=subprocess.PIPE).communicate(timeout=10)[0]
        
            if ' ' not in str(systemctl):
                log_write("INFO", "Service started", f"Service: {restartserv}")
                print(f"[OK] Service {restartserv} started\n")
                conn.send(b"[OK] Service started")
            else:
                log_write("ERROR", "Service not started", f"Service: {restartserv}")
                log_write("ERROR", systemctl.decode('UTF-8').replace('\n', ' '))
                print(f"\n[ERROR] Service {restartserv} not started\n")
                conn.send(b"[ERROR] Service not started")
    else:
        log_write("ERROR", "Invalid api key")
        print("[ERROR] Invalid api key\n")
        conn.send(b"[ERROR] Invalid api key")


def Parse_Http(req):
    data = str(req).split(r"\r\n")
    req = str(req)

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
    
    return req, headers


def log_write(loglevel, msg, *attrs):
    logfile = open(log_path, 'a')
    
    logfile.write(f"[{datetime.now().strftime('%d.%m.%Y_%X')}][INFO](")
    logfile.write(','.join([(f'"{head}={headers[head]}"') for head in headers]))

    logfile.write(f")\n[{datetime.now().strftime('%d.%m.%Y_%X')}]")
    logfile.write(f"[{loglevel}]({msg})")
    logfile.write(f"({', '.join([(f'{attr}') for attr in attrs])});\n")

    logfile.close()


strings = ['Host: ',
           'User-Agent: ',
           'Content-Type: ',
           ]

headers = dict()


while True:
    conn, addr = sock.accept()
    req = conn.recv(1024)

    try:
        req, headers = Parse_Http(req)

        if "POST" in headers['Method']:
            if 'json' in headers['Content-Type']:
                startjson = req.find('{')
                endjson = req.find('}')
                json_data = req[startjson:endjson+1]
                json_file = json.loads(json_data)

                restartservice = parse_serv_dict(json_file['service_name'])

                restart_service(restartservice, json_file['api_key'])
            else:
                print(f"[Error] Missing JSON data\n")
                conn.send(b"Error: Missing JSON data")
                log_write("Error", "Missing JSON data")
        else:
            print(f"[Error] Wrong method {headers['Method']}\n")
            conn.send(b"Error: Wrong method")
            log_write("Error", f"Wrong method {headers['Method']}")

    except KeyError as exception:
        conn.send(b"Error: " + exception)
        print(f"{exception}r\n")
        log_write("Error", exception)

    except Exception as exception:
        conn.send(b"Error: exception")
        print(f"{exception}r\n")
        log_write("Error", exception)

conn.close()