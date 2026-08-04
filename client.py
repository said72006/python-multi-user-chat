"""
Client program for TCP chat application.
"""

import socket
import threading


HOST = "127.0.0.1"
PORT = 5000



# Create TCP socket
client_socket = socket.socket(
    socket.AF_INET,
    socket.SOCK_STREAM
)



try:

    # Connect to server
    client_socket.connect(
        (HOST, PORT)
    )

    print("Connected to server")


except Exception as e:

    print("Connection error:", e)

    exit()



# Choose unique nickname

while True:

    nickname = input("Enter your name: ")


    client_socket.send(
        nickname.encode()
    )


    response = (
        client_socket.recv(1024)
        .decode()
    )


    if response == "NAME_TAKEN":

        print("Name already exists, try another one")


    else:

        break





def receive():
    """
    Receive messages from server.
    Runs in a separate thread.
    """

    while True:

        try:

            message = client_socket.recv(1024)


            if not message:

                print("Server disconnected")

                break



            print(
                "\n" + message.decode()
            )



        except Exception as e:

            print(
                "Receive error:",
                e
            )

            break





# Thread for receiving messages

receive_thread = threading.Thread(
    target=receive,
    daemon=True
)


receive_thread.start()





# Sending messages

while True:

    try:

        message = input("You: ")


        if message.lower() == "exit":

            print("Leaving chat...")

            break



        client_socket.send(
            message.encode()
        )



    except Exception as e:

        print(
            "Send error:",
            e
        )

        break




# Close connection

client_socket.close()