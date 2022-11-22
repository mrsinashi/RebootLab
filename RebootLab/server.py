import socket
import json
import subprocess

secure_key = "]<9A'QNWb8_"
port = 9183

sock = socket.socket()
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind(('', port))
sock.listen(5)
print('Server is running, please, press ctrl+c to stop\n')


def kill_service(killserv, securekey):
    if securekey == secure_key:
        command = f"sudo systemctl status {killserv} | grep -P '└─|├─'| sed 's/.*─//' | sed -r 's/ .+//' | sed 's/[^0-9]*//g'"
        service_proc = subprocess.Popen([command], shell=True, stdout=subprocess.PIPE)
        pids = service_proc.communicate(timeout=10)[0].decode('utf-8').split()

        for pid in pids:
            print(f"PID {pid}: killing...")
            subprocess.Popen([f"sudo kill {pid}"], shell=True, stdout=subprocess.PIPE)

        service_proc2 = subprocess.Popen([f"sleep 1; {command}"], shell=True, stdout=subprocess.PIPE)
        pids2 = service_proc2.communicate(timeout=10)[0].decode('utf-8').split()
        
        for pid2 in pids2:
            if pid in pids2:
                print(f"Error killing PID: {pid}")
                conn.send(b"Error: service not killed:(")
            else:
                print(f"Killed: {pid}")
                conn.send(b"Killed")
    else:
        print("Error: Invalid secure key")
        conn.send(b"Error: Invalid secure key")


while True:
    conn, addr = sock.accept()
    data = conn.recv(1024)

    try:
        req = json.loads(data)

        rec_service_name = req['service_name']
        rec_secure_key = req['secure_key']

        kill_service(rec_service_name, rec_secure_key)
        print(f'Service Name: {rec_service_name}, Secure Key: "{rec_secure_key}"\n')

    except KeyError:
        conn.send(b"Error: Invalid keys")
        print("Error: Invalid keys\n")

    except Exception:
        conn.send(b"Error: unknown error")
        print("Error: unknown error\n")


conn.close()
