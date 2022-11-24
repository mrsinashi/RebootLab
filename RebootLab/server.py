import socket
import json
import subprocess
import time
from collections import deque

api_key = "+<9AkQNWb8_"
port = 9184

sock = socket.socket()
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind(('192.168.50.253', port))
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
          
            if "Active: active" in systemctl:
                for pid2 in pids2:
                    if pid in pids2:
                        print(f"Error: Restarting failed\n")
                        conn.send(b"Error: Restarting failed")
                    else:
                        print(f"OK: Restarting succes\n")
                        conn.send(b"OK: Restarting succes")
            else:
                print(f"Error: Restarting failed, service stoped\n")
        else:
            print(f"Service not running\n Starting...")
            systemctl = subprocess.Popen(f"sudo systemctl start {restartserv}", shell=True, stdout=subprocess.PIPE).communicate(timeout=10)[0]
            
            if str(systemctl) == "b''":
                print(f"Service {restartserv} started\n")
                conn.send(b"Service started")
            else:
                print(f"\nService {restartserv} not started\n")
                conn.send(b"Service not started")
    else:
        print("Error: Invalid api key\n")
        conn.send(b"Error: Invalid api key")


def Parse_Http(req):
    data = str(req).split(r"\r\n")
    req = str(req)

    headers['Fhirst'] = data[0]

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

                restart_service(json_file['service_name'], json_file['api_key'])
            else:
                print("Error: Invalid request\n")
                conn.send(b"Error: Invalid request")
        else:
            print("Error: Invalid request\n")
            conn.send(b"Error: Invalid request")

    except KeyError:
        conn.send(b"Error: Invalid keys")
        print("Error: Invalid keys\n")

    except Exception:
        conn.send(b"Error: unknown error")
        print("Error: unknown error\n")

conn.close()