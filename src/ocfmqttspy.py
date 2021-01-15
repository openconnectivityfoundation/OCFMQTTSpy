#!/usr/bin/env python
#############################
#
#    copyright 2020 Open Interconnect Consortium, Inc. All rights reserved.
#    Redistribution and use in source and binary forms, with or without modification,
#    are permitted provided that the following conditions are met:
#    1.  Redistributions of source code must retain the above copyright notice,
#        this list of conditions and the following disclaimer.
#    2.  Redistributions in binary form must reproduce the above copyright notice,
#        this list of conditions and the following disclaimer in the documentation and/or other materials provided
#        with the distribution.
#
#    THIS SOFTWARE IS PROVIDED BY THE OPEN INTERCONNECT CONSORTIUM, INC. "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES,
#    INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE OR
#    WARRANTIES OF NON-INFRINGEMENT, ARE DISCLAIMED. IN NO EVENT SHALL THE OPEN INTERCONNECT CONSORTIUM, INC. OR
#    CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
#    (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS;
#    OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
#    OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE,
#    EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
#############################

import paho.mqtt.client as mqtt
from paho.mqtt.packettypes import PacketTypes

import threading
import datetime
import queue
import signal
import time
import logging
import ssl
from random import randrange
import uuid

import json
from json.decoder import JSONDecodeError
import cbor

import argparse

import tkinter as tk
from tkinter.scrolledtext import ScrolledText
from tkinter import ttk, VERTICAL, HORIZONTAL, N, S, E, W

logger = logging.getLogger(__name__)

topic_queue = queue.Queue()


# The MQTTv5 callback takes the additional 'props' parameter.
def on_connect(client, userdata, flags, rc, props):
    """[summary]
    mqtt onconnect implementation (callback)
    Args:
        client : mqtt client
        userdata : mqtt userdata
        flags : mqtt flags
        rc : mqtt rc
        props : mqtt properties
    """
    my_string = "Connected with result code "+str(rc)
    print("===============")
    print(my_string)
    print("flags:", str(flags))
    logger.log(logging.INFO, my_string)
    client.subscribe("$SYS/broker/clients/connected")
    print(client)
    print(str(client._client_id))
    if hasattr(props, 'AssignedClientIdentifier'):
        client_id = props.AssignedClientIdentifier
        print("client_id:", client_id)


def on_disconnect(mqttc, obj, rc):
    """[summary]
    mqtt on_disconnect callback implementation
    Args:
        mqttc : mqtt client
        obj : mqtt object
        rc : mqtt rc
    """
    #mqttc.user_data_set(obj + 1)
    if obj == 0:
        mqttc.reconnect()


def on_message(client, userdata, message):
    data = message.payload
    data_str = "ERROR! not decoded"
    try:
        data_str = str(message.payload.decode("utf-8"))
    except:
        try:
            json_data = cbor.loads(data)
            data_str = json.dumps(json_data, indent=2, sort_keys=True)
            data_str = "\n" + data_str
        except:
            pass

    print("---------- ")
    print("message received ", data_str)
    print("message topic=", message.topic)
    print("message qos=", message.qos)
    print("message retain flag=", message.retain)

    additional_data = " "
    try:
        props = message.properties
        if hasattr(props, 'CorrelationData'):
            print(" Correlation ID", props.CorrelationData)
            additional_data += "correlation ID :" + \
                str(props.CorrelationData) + " "
        if hasattr(props, 'ResponseTopic'):
            print("ResponseTopic ", props.ResponseTopic)
            additional_data += "Response Topic:" + str(props.ResponseTopic)
    except NameError:
        pass

    my_string = "received: " + str(message.topic) + " QOS: " + str(
        message.qos) + " Retain: " + str(message.retain) + " " + additional_data + data_str
    logger.log(logging.INFO, my_string)


def on_unsubscribe(client, userdata, mid):
    print("---------- ")
    print("unsubscribing ", mid)


class QueueHandler(logging.Handler):
    """Class to send logging records to a queue
    It can be used from different threads
    The ConsoleUi class polls this queue to display records in a ScrolledText widget
    """
    # Example from Moshe Kaplan: https://gist.github.com/moshekaplan/c425f861de7bbf28ef06
    # (https://stackoverflow.com/questions/13318742/python-logging-to-tkinter-text-widget) is not thread safe!
    # See https://stackoverflow.com/questions/43909849/tkinter-python-crashes-on-new-thread-trying-to-log-on-main-thread

    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record):
        self.log_queue.put(record)


class ConsoleUi:
    """Poll messages from a logging queue and display them in a scrolled text widget"""

    def __init__(self, frame):
        self.frame = frame
        # Create a ScrolledText wdiget
        self.scrolled_text = ScrolledText(frame, state='disabled', height=40)
        self.scrolled_text.grid(row=0, column=0, sticky=(N, S, W, E))
        self.scrolled_text.configure(font='TkFixedFont')
        self.scrolled_text.tag_config('INFO', foreground='black')
        self.scrolled_text.tag_config('DEBUG', foreground='gray')
        self.scrolled_text.tag_config('WARNING', foreground='orange')
        self.scrolled_text.tag_config('ERROR', foreground='red')
        self.scrolled_text.tag_config(
            'CRITICAL', foreground='red', underline=1)
        # Create a logging handler using a queue
        self.log_queue = queue.Queue()
        self.queue_handler = QueueHandler(self.log_queue)
        formatter = logging.Formatter('%(asctime)s: %(message)s')
        self.queue_handler.setFormatter(formatter)
        logger.addHandler(self.queue_handler)
        # Start polling messages from the queue
        self.frame.after(100, self.poll_log_queue)

    def display(self, record):
        msg = self.queue_handler.format(record)
        self.scrolled_text.configure(state='normal')
        self.scrolled_text.insert(tk.END, msg + '\n', record.levelname)
        self.scrolled_text.configure(state='disabled')
        # Autoscroll to the bottom
        self.scrolled_text.yview(tk.END)

    def poll_log_queue(self):
        # Check every 100ms if there is a new message in the queue to display
        while True:
            try:
                record = self.log_queue.get(block=False)
            except queue.Empty:
                break
            else:
                self.display(record)
        self.frame.after(100, self.poll_log_queue)


class FormUi:

    def __init__(self, frame):
        self.frame = frame

        # Create a combobbox to select the logging level
        values = ['0', '1', '2']
        self.level = tk.StringVar()
        ttk.Label(self.frame, text='QOS Level:').grid(
            column=0, row=0, sticky=W)
        self.combobox = ttk.Combobox(
            self.frame,
            textvariable=self.level,
            width=25,
            state='readonly',
            values=values
        )
        self.combobox.current(0)
        self.combobox.grid(column=1, row=0, sticky=(W, E))

        # Retain
        LABEL0, LABEL1 = '0', '1'
        self.btn_var = tk.StringVar(self.frame, LABEL0)
        ttk.Label(self.frame, text='Retain:').grid(column=0, row=1, sticky=W)
        ttk.Checkbutton(self.frame, textvariable=self.btn_var, width=12, variable=self.btn_var,
                        offvalue=LABEL0, onvalue=LABEL1).grid(column=1, row=1, sticky=(W, E))

        # Create a text field to enter a Topic
        self.topic = tk.StringVar()
        ttk.Label(self.frame, text='Topic:').grid(column=0, row=2, sticky=W)
        ttk.Entry(self.frame, textvariable=self.topic, width=25).grid(
            column=1, row=2, sticky=(W, E))
        self.topic.set('OCF/*/oic%2Fd/R')

        # Create a text field to enter the data to be published
        self.data = tk.StringVar()
        ttk.Label(self.frame, text='Message:').grid(column=0, row=3, sticky=W)
        #ttk.Entry(self.frame, textvariable=self.data, width=25, height=20).grid(column=1, row=2, sticky=(W, E))
        ttk.Entry(self.frame, textvariable=self.data, width=25).grid(
            column=1, row=3, sticky=(W, E))
        self.data.set('{ "value" : true }')

        # Add a button to publish the message as text
        self.button = ttk.Button(
            self.frame, text='Publish', command=self.submit_cbor)
        self.button.grid(column=0, row=4, sticky=W)

        # Add a button to publish the message as cbor
        #self.button = ttk.Button(
        #    self.frame, text='Publish CBOR', command=self.submit_cbor)
        #self.button.grid(column=1, row=4, sticky=W)

        # Add a button to publish the message as cbor
        self.button = ttk.Button(
            self.frame, text='Discover oic/res', command=self.submit_disc)
        self.button.grid(column=1, row=4, sticky=W)
        
        
        # Add a button to publish the message as cbor
        self.button = ttk.Button(
            self.frame, text='Test', command=self.submit_test)
        #self.button.grid(column=0, row=6, sticky=W)

    def submit_message(self):
        my_data = self.data.get()
        my_topic = self.topic.get()
        my_qos = self.level.get()
        my_qos_int = int(my_qos)
        my_retain = self.btn_var.get()
        retain_flag = True
        if my_retain == "1":
            retain_flag = True

        additional_data = ""
        props = None
        last_topic = my_topic.split("/")[-1]
        if last_topic in ["C","R","U","D","N"]:
            return_topic = self.app.client.my_udn
            props = mqtt.Properties(PacketTypes.PUBLISH)
            random_number = randrange(100000)
            random_string = str(random_number)
            props.CorrelationData = random_string.encode("utf-8")
            props.ResponseTopic = return_topic
            additional_data += "\ncorr Id: " + \
                str(props.CorrelationData) + \
                " Response Topic: " + props.ResponseTopic

        my_string = "publish: "+str(self.topic.get()) + " QOS: " + my_qos + \
            " Retain: " + my_retain + " " + my_data + additional_data
        logger.log(logging.INFO, my_string)
        print(my_string)
        topic_queue.put({my_topic, props.CorrelationData})
        self.app.client.publish(
            my_topic, my_data, my_qos_int, retain_flag, properties=props)

    def submit_cbor(self):
        my_data = self.data.get()
        cbor_data = None
        if my_data is not None and len(my_data) > 2:
            try:
                json_data = json.loads(my_data)
            except JSONDecodeError as e:
                # do whatever you want
                logger.log(logging.ERROR, e)
                return
            except TypeError as e:
                # do whatever you want in this case
                logger.log(logging.ERROR, e)
                return
            cbor_data = cbor.dumps(json_data)
        my_topic = self.topic.get()
        my_qos = self.level.get()
        my_qos_int = int(my_qos)
        my_retain = self.btn_var.get()
        print(" ====> RETAIN", my_retain)
        retain_flag = False
        if my_retain == "1":
            print("retain is true")
            retain_flag = True

        additional_data = " "
        props = None
        last_topic = my_topic.split("/")[-1]
        if last_topic in ["C","R","U","D","N"]:
            return_topic = self.app.client.my_udn
            props = mqtt.Properties(PacketTypes.PUBLISH)
            random_number = randrange(100000)
            random_string = str(random_number)
            props.CorrelationData = random_string.encode("utf-8")
            props.ResponseTopic = return_topic
            additional_data = "\ncorr Id: " + \
                str(props.CorrelationData) + \
                " Response Topic: " + props.ResponseTopic

        my_string = "publish: "+str(self.topic.get()) + " QOS: " + my_qos + \
            " Retain: " + my_retain + " " + my_data + additional_data
        logger.log(logging.INFO, my_string)
        topic_queue.put({my_topic, props.CorrelationData})
        print(my_string)
        ret = self.app.client.publish(my_topic, cbor_data,
                                my_qos_int, retain_flag, properties=props)
                 
    def submit_disc(self):
        my_data = self.data.get()
        cbor_data = None
        if my_data is not None and len(my_data) > 2:
            try:
                json_data = json.loads(my_data)
            except JSONDecodeError as e:
                # do whatever you want
                logger.log(logging.ERROR, e)
                return
            except TypeError as e:
                # do whatever you want in this case
                logger.log(logging.ERROR, e)
                return
            cbor_data = cbor.dumps(json_data)
        my_topic = "OCF/*/oic%2Fres/R"
        my_qos = self.level.get()
        my_qos_int = int(my_qos)
        my_retain = self.btn_var.get()
        print(" ====> RETAIN", my_retain)
        retain_flag = False
        if my_retain == "1":
            print("retain is true")
            retain_flag = True

        additional_data = " "
        props = None
        last_topic = my_topic.split("/")[-1]
        if last_topic in ["C","R","U","D","N"]:
            return_topic = self.app.client.my_udn
            props = mqtt.Properties(PacketTypes.PUBLISH)
            random_number = randrange(100000)
            random_string = str(random_number)
            props.CorrelationData = random_string.encode("utf-8")
            props.ResponseTopic = return_topic
            additional_data = "\ncorr Id: " + \
                str(props.CorrelationData) + \
                " Response Topic: " + props.ResponseTopic

        my_string = "publish: "+str(self.topic.get()) + " QOS: " + my_qos + \
            " Retain: " + my_retain + " " + my_data + additional_data
        logger.log(logging.INFO, my_string)
        topic_queue.put({my_topic, props.CorrelationData})
        print(my_string)
        ret = self.app.client.publish(my_topic, cbor_data,
                                my_qos_int, retain_flag, properties=props)


    def submit_test(self):
        cbor_data = None
        my_qos = self.level.get()
        my_qos_int = int(my_qos)
        my_retain = self.btn_var.get()
        retain_flag = False
        if my_retain == "1":
            print("retain is true")
            retain_flag = True
        # /oic/res
        my_topic = "OCF/*/oic%2Fres/R"  
        props = mqtt.Properties(PacketTypes.PUBLISH)
        random_number = randrange(100000)
        random_string = str(random_number)
        props.CorrelationData = random_string.encode("utf-8")
        props.ResponseTopic = self.app.client.my_udn
        ret = self.app.client.publish(my_topic, cbor_data,
                                my_qos_int, retain_flag, properties=props)
                                        
        my_topic = "OCF/*/oic%2Fres?if=oic.if.baseline/R"  
        props = mqtt.Properties(PacketTypes.PUBLISH)
        random_number = randrange(100000)
        random_string = str(random_number)
        props.CorrelationData = random_string.encode("utf-8")
        props.ResponseTopic = self.app.client.my_udn
        ret = self.app.client.publish(my_topic, cbor_data,
                                my_qos_int, retain_flag, properties=props)

        my_topic = "OCF/*/oic%2Fres?if=oic.if.ll/R"  
        props = mqtt.Properties(PacketTypes.PUBLISH)
        random_number = randrange(100000)
        random_string = str(random_number)
        props.CorrelationData = random_string.encode("utf-8")
        props.ResponseTopic = self.app.client.my_udn
        ret = self.app.client.publish(my_topic, cbor_data,
                                my_qos_int, retain_flag, properties=props)
                                
        my_topic = "OCF/*/oic%2Fres?if=oic.if.b/R"  
        props = mqtt.Properties(PacketTypes.PUBLISH)
        random_number = randrange(100000)
        random_string = str(random_number)
        props.CorrelationData = random_string.encode("utf-8")
        props.ResponseTopic = self.app.client.my_udn
        ret = self.app.client.publish(my_topic, cbor_data,
                                my_qos_int, retain_flag, properties=props)
                                
        # /oic/p                      
        my_topic = "OCF/*/oic%2Fp/R"  
        props = mqtt.Properties(PacketTypes.PUBLISH)
        random_number = randrange(100000)
        random_string = str(random_number)
        props.CorrelationData = random_string.encode("utf-8")
        props.ResponseTopic = self.app.client.my_udn
        ret = self.app.client.publish(my_topic, cbor_data,
                                my_qos_int, retain_flag, properties=props)

        my_topic = "OCF/*/oic%2Fp?if=oic.if.r/R"  
        props = mqtt.Properties(PacketTypes.PUBLISH)
        random_number = randrange(100000)
        random_string = str(random_number)
        props.CorrelationData = random_string.encode("utf-8")
        props.ResponseTopic = self.app.client.my_udn
        ret = self.app.client.publish(my_topic, cbor_data,
                                my_qos_int, retain_flag, properties=props)
                     
        # /oic/d                        
        my_topic = "OCF/*/oic%2Fd/R"  
        props = mqtt.Properties(PacketTypes.PUBLISH)
        random_number = randrange(100000)
        random_string = str(random_number)
        props.CorrelationData = random_string.encode("utf-8")
        props.ResponseTopic = self.app.client.my_udn
        ret = self.app.client.publish(my_topic, cbor_data,
                                my_qos_int, retain_flag, properties=props)
                                
        my_topic = "OCF/*/oic%2Fd?if=oic.if.r/R"  
        props = mqtt.Properties(PacketTypes.PUBLISH)
        random_number = randrange(100000)
        random_string = str(random_number)
        props.CorrelationData = random_string.encode("utf-8")
        props.ResponseTopic = self.app.client.my_udn
        ret = self.app.client.publish(my_topic, cbor_data,
                                my_qos_int, retain_flag, properties=props)


class ThirdUi:

    def __init__(self, frame):
        self.frame = frame
        labelText = tk.StringVar()
        self.label = ttk.Label(self.frame, textvariable=labelText).grid(
            column=0, row=1, sticky=W)
        #ttk.Label(self.frame, text='With another line here!').grid(
        #    column=0, row=4, sticky=W)


class App:

    def __init__(self, root):
        self.root = root
        root.title('OCF MQTT Spy')
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)
        # Create the panes and frames
        vertical_pane = ttk.PanedWindow(self.root, orient=VERTICAL)
        vertical_pane.grid(row=0, column=0, sticky="nsew")
        horizontal_pane = ttk.PanedWindow(vertical_pane, orient=HORIZONTAL)

        vertical_pane.add(horizontal_pane)
        form_frame = ttk.Labelframe(
            horizontal_pane, text="Publish Information")
        form_frame.columnconfigure(1, weight=1)
        horizontal_pane.add(form_frame, weight=1)

        console_frame = ttk.Labelframe(horizontal_pane, text="Console")
        console_frame.columnconfigure(0, weight=1)
        console_frame.rowconfigure(0, weight=1)
        horizontal_pane.add(console_frame, weight=1)

        third_frame = ttk.Labelframe(vertical_pane, text="Return topic info")
        vertical_pane.add(third_frame, weight=1)

        # Initialize all frames
        self.form = FormUi(form_frame)
        self.form.app = self
        self.console = ConsoleUi(console_frame)
        self.console.app = self
        self.third = ThirdUi(third_frame)
        self.third.app = self
        #self.third.labelText.set('OCF/*/oic%2Fd/R')
        self.root.protocol('WM_DELETE_WINDOW', self.quit)
        self.root.bind('<Control-q>', self.quit)
        signal.signal(signal.SIGINT, self.quit)

    def quit(self, *args):
        # unsubscribe from the topic
        self.client.unsubscribe(self.subscribe_topic)
        self.client.loop_stop()
        self.client.disconnect()

        self.root.destroy()


def random_string():
    x = uuid.uuid1()
    return str(x)


def main():
    # commandline arguments to the application, so that the app is quite generic to use.
    parser = argparse.ArgumentParser()
    parser.add_argument('-H', '--host', required=False,
                        default="192.168.178.89")
    parser.add_argument('-c', '--clientid', required=False, default=None)
    parser.add_argument('-u', '--username', required=False, default=None)
    #parser.add_argument('-d', '--disable-clean-session', action='store_true', help="disable 'clean session' (sub + msgs not cleared when client disconnects)")
    parser.add_argument('-p', '--password', required=False, default=None)
    parser.add_argument('-P', '--port', required=False, type=int,
                        default=None, help='Defaults to 8883 for TLS or 1883 for non-TLS')
    parser.add_argument('-k', '--keepalive',
                        required=False, type=int, default=60)
    parser.add_argument('-s', '--use-tls', action='store_true')
    parser.add_argument('--insecure', action='store_true')
    parser.add_argument('-F', '--cacerts', required=False, default=None)
    parser.add_argument('--tls-version', required=False, default=None,
                        help='TLS protocol version, can be one of tlsv1.2 tlsv1.1 or tlsv1\n')
    #parser.add_argument('-D', '--debug', action='store_true')

    #args = parser.parse_args()
    args, unknown = parser.parse_known_args()

    logging.basicConfig(level=logging.DEBUG)

    #
    # default values
    broker = "192.168.178.89"
    client_id = None
    usetls = args.use_tls

    #
    #  handle arguments
    #
    broker = args.host
    if args.clientid == None:
        client_id = random_string()
    else:
        client_id = args.clientid
    port = args.port    
    if port is None:
      if usetls:
        port = 8883
      else:
        port = 1883
    keep_alive = args.keepalive

    # create the client
    client = mqtt.Client(client_id, protocol=mqtt.MQTTv5) #, clean_session = not args.disable_clean_session)

    if usetls:
        if args.tls_version == "tlsv1.2":
          tlsVersion = ssl.PROTOCOL_TLSv1_2
        elif args.tls_version == "tlsv1.1":
          tlsVersion = ssl.PROTOCOL_TLSv1_1
        elif args.tls_version == "tlsv1":
          tlsVersion = ssl.PROTOCOL_TLSv1
        elif args.tls_version is None:
          tlsVersion = None
        else:
          print ("Unknown TLS version - ignoring")
          tlsVersion = None

        if not args.insecure:
            cert_required = ssl.CERT_REQUIRED
        else:
            cert_required = ssl.CERT_NONE
            
        client.tls_set(ca_certs=args.cacerts, certfile=None, keyfile=None, cert_reqs=cert_required, tls_version=tlsVersion)

        if args.insecure:
            client.tls_insecure_set(True)

    if args.username or args.password:
       client.username_pw_set(args.username, args.password)

    client.on_connect = on_connect
    client.on_message = on_message
    client.on_unsubscribe = on_unsubscribe
    client.on_disconnect = on_disconnect
    # connect the client, with supplied info
    client.connect(broker, port, keep_alive)
    client.loop_start()

    root = tk.Tk()
    app = App(root)
    app.client = client

    x = uuid.uuid1()
    client.my_udn = str(x)

    logger.log(logging.INFO, "broker :"+broker+"  port:"+str(port))
    logger.log(logging.INFO, "clientid :"+str(client_id))
    if args.username or args.password:
      logger.log(logging.INFO, "userid :"+str(args.username)+" password :"+str(args.password))

    app.subscribe_topic = "OCF/*/#"
    print("Subscribing to topic: ", app.subscribe_topic)
    logger.log(logging.INFO, "Subscribing to topic: " + str(app.subscribe_topic))
    my_val = client.subscribe(app.subscribe_topic, 2)
    print("subscription succeeded:", my_val)

    print("Subscribing to return topic: ", app.client.my_udn)
    logger.log(logging.INFO, "Subscribing to return topic: "+ str(app.client.my_udn))
    my_val = client.subscribe(app.client.my_udn, 2)
    print("subscription succeeded:", my_val)


    app.root.mainloop()


if __name__ == '__main__':
    main()
