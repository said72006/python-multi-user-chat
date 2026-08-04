"""
Multi-user chat server using TCP sockets and threading.
"""

import socket
import threading


HOST = "127.0.0.1"
PORT = 5000


# Create TCP socket
server_socket = socket.socket(
    socket.AF_INET,
    socket.SOCK_STREAM
)


# Allow reusing the port after restarting the server
server_socket.setsockopt(
    socket.SOL_SOCKET,
    socket.SO_REUSEADDR,
    1
)


try:

    # Bind server to IP and port
    server_socket.bind((HOST, PORT))

    # Start listening
    server_socket.listen()

    print("Server is running...")


except Exception as e:

    print("Server setup error:", e)

    server_socket.close()

    exit()



# Store clients: socket -> nickname
clients = {}



def nickname_exists(nickname):

    return nickname in clients.values()



def broadcast(message, sender=None):

    for client in list(clients.keys()):

        if client != sender:

            try:

                client.send(message)


            except Exception:

                client.close()

                if client in clients:
                    del clients[client]



def handle_client(client_socket):

    nickname = clients[client_socket]


    join_message = f"{nickname} joined the chat"

    print(join_message)

    broadcast(
        join_message.encode(),
        client_socket
    )


    while True:

        try:

            message = client_socket.recv(1024)


            if not message:
                break


            full_message = (
                f"{nickname}: {message.decode()}"
            )


            print(full_message)


            broadcast(
                full_message.encode(),
                client_socket
            )


        except Exception:

            print(f"{nickname} disconnected")

            break



    # Remove disconnected client

    client_socket.close()


    if client_socket in clients:

        del clients[client_socket]


    leave_message = f"{nickname} left the chat"

    print(leave_message)


    broadcast(
        leave_message.encode()
    )





# Main server loop

while True:

    try:

        # Accept client connection

        client_socket, address = server_socket.accept()


        print(
            "Connected:",
            address
        )


        # Receive nickname

        while True:

            nickname = (
                client_socket.recv(1024)
                .decode()
            )


            if nickname_exists(nickname):

                client_socket.send(
                    "NAME_TAKEN".encode()
                )


            else:

                clients[client_socket] = nickname


                client_socket.send(
                    "NAME_ACCEPTED".encode()
                )

                break



        # Create thread for this client

        thread = threading.Thread(
            target=handle_client,
            args=(client_socket,),
            daemon=True
        )


        thread.start()



    except Exception as e:

        print("Server error:", e)