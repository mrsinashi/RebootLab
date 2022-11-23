import socket
import json
import subprocess
import time
from collections import deque

secure_key = "]<9A'QNWb8_"
port = 9184

sock = socket.socket()
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind(('', port))
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
    

def restart_service(restartserv, securekey):
    if securekey == secure_key:
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
                        print(f"Error: Restarting failed")
                        conn.send(b"Error: Restarting failed")
                    else:
                        print(f"OK: Restarting succes")
                        conn.send(b"OK: Restarting succes")
            else:
                print(f"Error: Restarting failed, service stoped")
        else:
            print(f"Service not running\n Starting...")
            systemctl = subprocess.Popen(f"sudo systemctl start {restartserv}", shell=True, stdout=subprocess.PIPE).communicate(timeout=10)[0]

            if str(systemctl) == "b''":
                print(f"Service {restartserv} started")
                conn.send(b"Service started")
            else:
                print(f"Service {restartserv} not started")
                conn.send(b"Service not started")
    else:
        print("Error: Invalid secure key")
        conn.send(b"Error: Invalid secure key")


while True:
    conn, addr = sock.accept()
    data = conn.recv(1024)

    data = str(data).split(r"\r\n")
    
    print(data[9])
    req = data[9]
    req = req[0:-1]
    req = json.loads(str(req))
    print(req)
    i = 0

    for string in data:
        print(f'{i}: "{string}"\n')
        i=i+1
    
    '''try:
        req = json.loads(data)

        rec_service_name = req['service_name']
        rec_secure_key = req['secure_key']

        restart_service(rec_service_name, rec_secure_key)

    except KeyError:
        conn.send(b"Error: Invalid keys")
        print("Error: Invalid keys\n")

    except Exception:
        conn.send(b"Error: unknown error")
        print("Error: unknown error\n")'''


conn.close()