import socket

command = "124"

def send_tcp_ip_command(command: str):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect(("192.168.137.110", 50005))
            s.sendall(command.encode())
            response = s.recv(1024)
            return response.decode()
    except Exception as e:
        return str(e)


if __name__ == "__main__":
    print(send_tcp_ip_command(command))