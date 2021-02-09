#!/usr/bin/env python
#############################
#
#    copyright 2020-2021 Open Interconnect Consortium, Inc. All rights reserved.
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

import configparser
import os.path

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

# global variables
# the logger (in the window)
logger = logging.getLogger(__name__)
# topic queue, will contain list of [props.CorrelationData, my_topic, cb, udn]
# correlation id == returned correlation id by the responder
# my_topic == topic that was the request
# cb, function to be called
# udn, the udn of the responder
topic_queue = []
# global return topic, will be set by the application
return_topic = ""

def escape_url(url):
    """escape the url

    Args:
        url ([type]): [
    """
    my_url = url
    if my_url[0] == "/":
        my_url = my_url[1:]
    url_escaped = my_url.replace("/","%2F")
    return url_escaped

def oic_idd_cb(client, userdata, message, udn):
    """ call back for the IDD request
    Args:
        client (class): mqtt client
        userdata (not used): not used
        message (class): received mqtt message
        udn (string): udn, the responder udn
    """
    print ("oic_idd_cb")
    json_data = get_json_from_cbor_data_from_message(message)
    print (json_data)
    url = list_url_from_idd_res(json_data)
    print ("url", url)
    publish_url(client, client.my_udn, udn, url, "R", "oic_idd_file_cb")

def oic_idd_file_cb(client, userdata, message, udn):
    """ call back for the IDD file request
    Args:
        client (class): mqtt client
        userdata (not used): not used
        message (class): received mqtt message
        udn (string): udn, the responder udn
    """
    my_text = get_str_from_cbor_data_from_message(message)
    show_window_with_text("IDD:  "+udn, my_text)


def oic_residd_cb(client, userdata, message, udn):
    """ call back for the Res->IDD request
    Args:
        client (class): mqtt client
        userdata (not used): not used
        message (class): received mqtt message
        udn (string): udn, the responder udn
    """
    print ("oic_idd_cb")
    json_data = get_json_from_cbor_data_from_message(message)
    print (json_data)

    udn = list_udn_from_res(json_data)
    url = list_idd_url_from_res(json_data)
    print (" udn, url", udn, url)
    publish_url(client, message.topic, udn, url, "R", "oic_idd_cb")

def oic_d_cb(client, userdata, message, udn):
    """ call back for the oic/d request
    Args:
        client (class): mqtt client
        userdata (not used): not used
        message (class): received mqtt message
        udn (string): udn, the responder udn
    """
    my_text = get_str_from_cbor_data_from_message(message)
    show_window_with_text(" /oic/d response of: "+udn, my_text)

    
def oic_p_cb(client, userdata, message, udn):
    """ call back for the oic/p  request
    Args:
        client (class): mqtt client
        userdata (not used): not used
        message (class): received mqtt message
        udn (string): udn, the responder udn
    """
    my_text = get_str_from_cbor_data_from_message(message)
    show_window_with_text(" /oic/p response of: "+udn, my_text)

def oic_res_cb(client, userdata, message, udn):
    """ call back for the IDD file request
    Args:
        client (class): mqtt client
        userdata (not used): not used
        message (class): received mqtt message
        udn (string): udn, the responder udn
    """
    my_text = get_str_from_cbor_data_from_message(message)
    show_window_with_text(" /oic/res response of: "+udn, my_text)
    my_json = get_json_from_cbor_data_from_message(message)
    my_urls = list_resources_from_oic_res(my_json, filter=True)
    print (my_urls)
    url_text = ""
    for url in my_urls:
        url_escaped = escape_url(url[1])
        item_text = "rt "
        for item in url[0]:
            item_text += item + " "
        url_text += item_text +"\n"
        if "oic.if.s" in url[2]:
            url_text  += "OCF/"+udn+"/"+url_escaped+"/R\n"
        elif "oic.if.a" in url[2]:
            url_text  += "OCF/"+udn+"/"+url_escaped+"/R\n"
            url_text  += "OCF/"+udn+"/"+url_escaped+"/U\n"
        elif "oic.if.r" in url[2]:
            url_text  += "OCF/"+udn+"/"+url_escaped+"/R\n"
        elif "oic.if.rw" in url[2]:
            url_text  += "OCF/"+udn+"/"+url_escaped+"/R\n"
            url_text  += "OCF/"+udn+"/"+url_escaped+"/U\n"
        if "oic.if.baseline" in url[2]:
            url_text  += "OCF/"+udn+"/"+url_escaped+"?if=oic.if.baseline/R\n"

    show_window_with_text(" URLS of: "+udn, url_text)
    #mystring = 

def list_udn_from_res(json_data):
    """
    retrieve the udn from the oic/res return array (baseline)
    """
    if isinstance(json_data, list) == False:
        return ""
    for data in json_data:
        if data.get("anchor"):
            udn = data.get("anchor")
            udn = udn[6:]
            return udn
    
def list_idd_url_from_res(json_data):
    """
    retrieve the udn from the oic/res return array (baseline)
    """
    if isinstance(json_data, list) == False:
        return ""
    for data in json_data:
        if data.get("rt"):
            if "oic.wk.introspection" in data.get("rt"):
               return  data.get("href")
    
def list_url_from_idd_res(json_data):
    """
    retrieve the udn from the oic/res return array (baseline)
    """
    if isinstance(json_data, dict) == False:
        return ""
    data = json_data.get("urlInfo")
    for my_items in data:
        #print (" ===> data ==\n", my_items, type(my_items))
        if my_items.get("content-type"):
            if "application/cbor" in my_items.get("content-type"):
               return  my_items.get("url")
    

def list_resources_from_oic_res(json_data, filter=False):
    """
    retrieve the list of resources from the oic/res return array (baseline)
    filter = remove oic.wk.* resources from the list
    """
    if isinstance(json_data, list) == False:
        return ""
    urllist = []
    for data in json_data:
        rt = data.get("rt")
        if rt:
            if filter == False:
                urllist.append([rt, data.get("href"), data.get("if")])
            else:
              for rt_value in rt:
                if rt_value.startswith("oic.wk.") == False:
                    urllist.append([rt, data.get("href"), data.get("if")])
                    break
    return urllist
    
def get_json_from_cbor_data_from_message(message):
    """retrieves the data as json, when the input is cbor
    Args:
        message mqtt: message
    Returns:
        json : data as json
    """
    json_data = []
    try:
        json_data = cbor.loads(message.payload)
    except:
        pass
    return json_data

def get_str_from_cbor_data_from_message(message):
    """retrieves the data as string, when the input is cbor
    Args:
        message mqtt: message
    Returns:
        string : data as string
    """
    data_str = ""
    try:
        json_data = cbor.loads(message.payload)
        data_str = json.dumps(json_data, indent=2, sort_keys=True)
        data_str = "\n" + data_str
    except:
        pass
    return data_str

def publish_url(client, return_topic, udn, url, command=None, cb=None, message=None ):
    """publish the message
       udn + url as topic with optional command
    Args:
        client (mqtt): mqtt client
        return_topic (string): return topic
        udn (string): udn of the target device
        url (string): url of the target
        command (string, optional): command e.g. CRUDN. Defaults to None.
        cb (function name, optional): callback function. Defaults to None.
        message (any, optional): message to be published . Defaults to None.
    """
    my_url = url
    my_qos_int = 0
    retain_flag = False
    cbor_data = message
    if my_url[0] == "/":
      my_url = my_url[1:]
    my_url = my_url.replace("/","%2F")
    my_topic = "OCF/"+udn+"/"+my_url
    if command is not None:
        if command in ["C","R","U","D","N"]:
           my_topic += "/"+command
        else:
           logger.log(logging.ERROR, "command not in CRUDN:"+command)
    props = mqtt.Properties(PacketTypes.PUBLISH)
    random_number = randrange(100000)
    random_string = str(random_number)
    props.CorrelationData = random_string.encode("utf-8")
    props.ResponseTopic = return_topic
    print (" publish_url publish request:", my_topic, random_string )
    topic_queue.append([props.CorrelationData, my_topic, cb, udn])
    ret = client.publish(my_topic, cbor_data,
                            my_qos_int, retain_flag, properties=props) 

# The MQTTv5 callback takes the additional 'props' parameter.
def on_connect(client, userdata, flags, rc, props):
    """on connect callback
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
    """on_disconnect callback
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
    """ on message callback
    mqtt on_message callback implementation
    Args:
        client : mqtt client
        userdata : not used
        message : received mqtt message
    """
    data = message.payload
    data_str = "ERROR! not decoded"
    correlation_id = 0
    json_data = []
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
    #print("message received ", data_str)
    print("message topic=", message.topic)
    print("message qos=", message.qos)
    print("message retain flag=", message.retain)

    additional_data = " "
    try:
        props = message.properties
        if hasattr(props, 'CorrelationData'):
            print("message Correlation ID", props.CorrelationData)
            correlation_id = props.CorrelationData
            additional_data += "correlation ID :" + \
                str(props.CorrelationData) + " "
        if hasattr(props, 'ResponseTopic'):
            print("message ResponseTopic ", props.ResponseTopic)
            additional_data += "Response Topic:" + str(props.ResponseTopic)
    except NameError:
        pass

    response_of_message = ""
    if correlation_id != 0:
        remove_job = None
        for job in topic_queue:
            print ("job", job)
            if job[0] == correlation_id:
                response_of_message = " response on: " + job[1]
                if  "/*/" in job[1]:
                    print ("discovery")
                    if "/*/oic%2Fres" in job[1]:
                        udn = list_udn_from_res(json_data)
                        print(" UDN from RES", udn)
                        # check if the udn is already listed..
                        ldata  = app.form.l1.get(0, "end")
                        if udn not in ldata:
                            app.form.l1.insert(0, udn)
                            app.form.l1.selection_set(0)
                else:
                    print ("not discovery")
                    remove_job = job
                    if job[2] is not None:
                        globals()[job[2]](client, userdata, message, job[3])  

            elif  "/*/" in job[1]:
                # remove another correlation_id that is a discovery
                remove_job = job
        if remove_job is not None:
            topic_queue.remove(remove_job)

    my_string = "received: " + str(message.topic) + " QOS: " + str(
        message.qos) + " Retain: " + str(message.retain) + " " +  response_of_message + additional_data + data_str
    logger.log(logging.INFO, my_string)

def on_unsubscribe(client, userdata, mid):
    """ on unsubscribe callback
    mqtt on_unsubcribe callback implementation
    Args:
        client : mqtt client
        userdata : not used
        mid : received mqtt message
    """
    print("---------- ")
    print("unsubscribing ", mid)

def show_window_with_text(window_name, my_text):
    """ call back for the IDD file request
    Args:
        client (class): mqtt client
        userdata (not used): not used
        message (class): received mqtt message
        udn (string): udn, the responder udn
    """
    window = tk.Toplevel()
    window.title(window_name) 
    text_area = ScrolledText(window,  
                                      wrap = tk.WORD,  
                                      width = 80,  
                                      height = 50 ) 
    text_area.grid(column = 0, pady = 10, padx = 10) 
    text_area.insert(tk.INSERT,my_text)
    text_area.configure(state ='disabled') 


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

        my_width = 45
        # Create a text field to enter the Message to be published
        ttk.Label(self.frame, text='Message:').grid(column=0, row=7, sticky=W)
        self.message_entry = ScrolledText(self.frame, width=my_width, height=3)
        self.message_entry.grid(column=1, row=7, sticky=W)
        self.message_entry.insert(tk.END,'{ "value" : true }')
        row_index = 10
        row_index += 1

        # Add a button to publish the message as cbor
        tk.Label(self.frame, text=' ').grid(column=0, row=row_index, sticky=W)
        self.button = ttk.Button(
            self.frame, text='Publish', command=self.submit_cbor)
        self.button.grid(column=1, row=row_index, sticky=W)

        row_index += 1 
        ttk.Label(self.frame, text='   ').grid(column=0, row=row_index, sticky=W)

        row_index += 1 
        # Add a button to do discovery
        tk.Label(self.frame, text='Discovery (*)').grid(column=0, row=row_index, sticky=W)
        self.button = ttk.Button(
            self.frame, text='Discover oic/res', command=self.submit_disc)
        self.button.grid(column=1, row=row_index, sticky=W)

        row_index += 1
        # list box section
        tk.Label(self.frame, text='Discovered:').grid(column=0, row=row_index, sticky=W)
        #len_max = len(random_string())
        self.l1 = tk.Listbox(self.frame, height=3, width = my_width)
        self.l1.grid(column=1, row=row_index, sticky=W)
       
        row_index += 3
        # Add a button to publish the message as cbor
        self.button_clear = ttk.Button(
            self.frame, text='Clear', command=self.submit_clear)
        self.button_clear.grid(column=0, row=row_index, sticky=W)

        row_index += 1
        # Add a button for oic/d
        tk.Label(self.frame, text='Retrieve :').grid(column=0, row=row_index, sticky=W)
        self.button = ttk.Button(
            self.frame, text='oic/d', command=self.submit_D)
        self.button.grid(column=1, row=row_index, sticky=W)
       
        row_index += 1
        # Add a button for oic/res
        tk.Label(self.frame, text='Retrieve :').grid(column=0, row=row_index, sticky=W)
        self.button = ttk.Button(
            self.frame, text='oic/res', command=self.submit_res)
        self.button.grid(column=1, row=row_index, sticky=W)
        row_index += 1
        # Add a button for oic/p
        tk.Label(self.frame, text='Retrieve :').grid(column=0, row=row_index, sticky=W)
        self.button = ttk.Button(
            self.frame, text='oic/p', command=self.submit_P)
        self.button.grid(column=1, row=row_index, sticky=W)
        
        row_index += 1
        # Add a button to retrieve the IDD file
        tk.Label(self.frame, text='Retrieve :').grid(column=0, row=row_index, sticky=W)
        self.button_idd = ttk.Button(
            self.frame, text='IDD', command=self.submit_IDD)
        self.button_idd.grid(column=1, row=row_index, sticky=W)

    def submit_cbor(self):
        """ publish the data
        read the topic from screen
        read the message, convert it to cbor
        add qos level & retain info
        if command, then add return topic and corrolation id.
        publish the data  
        """
        my_data = self.message_entry.get('1.0', tk.END)
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
        topic_queue.append([props.CorrelationData, my_topic, None, None])
        ret = self.app.client.publish(my_topic, cbor_data,
                                my_qos_int, retain_flag, properties=props)
                 
    def submit_disc(self):
        """ publish the oic/res discovery

        publish the data  
        """
        my_data = "" # no input for discovery
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
        topic_queue.append([props.CorrelationData, my_topic, None, None])
        print(my_string)
        ret = self.app.client.publish(my_topic, cbor_data,
                                my_qos_int, retain_flag, properties=props)


    def submit_IDD(self):
        """ get the IDD list
           will set a sequence of actions in play:
           - get oic/res from the device (with UDN) from the list
           - get the url of the IDD resource
           - get the url of the IDD file
           - show the IDD file in a popup window
        """
        # get the selected value of the listbox
        if self.l1.curselection() == ():
            return
        index = int(self.l1.curselection()[0])
        value = self.l1.get(index)
        print ("You selected item ",index, value)

        cbor_data = None
        my_qos = self.level.get()
        my_qos_int = int(my_qos)
        my_retain = self.btn_var.get()
        retain_flag = False
        if my_retain == "1":
            print("retain is true")
            retain_flag = True
        # /oic/res
        publish_url(self.app.client, self.app.client.my_udn, value, "/oic/res", "R", cb="oic_residd_cb") 

        
    def submit_D(self):
        """ get the oic/d data
           will set a sequence of actions in play:
           - get oic/d from the device (with UDN) from the list
           - show the response in a popup window
        """
        # get the selected value of the listbox
        if self.l1.curselection() == ():
            return
        index = int(self.l1.curselection()[0])
        value = self.l1.get(index)
        print ("You selected item ",index, value)

        cbor_data = None
        my_qos = self.level.get()
        my_qos_int = int(my_qos)
        my_retain = self.btn_var.get()
        retain_flag = False
        if my_retain == "1":
            print("retain is true")
            retain_flag = True
        # /oic/res
        publish_url(self.app.client, self.app.client.my_udn, value, "/oic/d", "R",  cb="oic_d_cb") 


    def submit_res(self):
        """ get the oic/res data
           will set a sequence of actions in play:
           - get oic/res from the device (with UDN) from the list
           - get the url of the IDD resource
           - get the url of the IDD file
           - show the IDD file in a popup window
        """
        # get the selected value of the listbox
        if self.l1.curselection() == ():
            return
        index = int(self.l1.curselection()[0])
        value = self.l1.get(index)
        print ("You selected item ",index, value)

        cbor_data = None
        my_qos = self.level.get()
        my_qos_int = int(my_qos)
        my_retain = self.btn_var.get()
        retain_flag = False
        if my_retain == "1":
            print("retain is true")
            retain_flag = True
        # /oic/res
        publish_url(self.app.client, self.app.client.my_udn, value, "/oic/res", "R",  cb="oic_res_cb") 


    def submit_P(self):
        """ get the oic/p data
           will set a sequence of actions in play:
           - get oic/p from the device (with UDN) from the list
           - show the response in a popup window
        """
        # get the selected value of the listbox
        if self.l1.curselection() == ():
            return
        index = int(self.l1.curselection()[0])
        value = self.l1.get(index)
        print ("You selected item ",index, value)

        cbor_data = None
        my_qos = self.level.get()
        my_qos_int = int(my_qos)
        my_retain = self.btn_var.get()
        retain_flag = False
        if my_retain == "1":
            print("retain is true")
            retain_flag = True
        # /oic/res
        publish_url(self.app.client, self.app.client.my_udn, value, "/oic/p", "R", cb="oic_p_cb") 


    def submit_clear(self):
        """ clear the discovered device list
        """
        print ("Clear - delete all entries")
        self.l1.delete(0,'end')

class ThirdUi:

    def __init__(self, frame):
        """ third (bottom) pane
        """
        self.frame = frame


        self.return_topic = tk.StringVar()
        ttk.Label(self.frame, text='Return Topic:').grid(column=0, row=2, sticky=W)
        entry = ttk.Entry(self.frame, state='disabled', textvariable=self.return_topic, width=100).grid(
            column=1, row=2, sticky=(W, E))


class App:

    def __init__(self, root):
        """ create the application, having 3 panes.
        """
        self.root = root
        root.title('OCF MQTT Spy')


        menubar = tk.Menu(root)
        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="Config", command=donothing)
        filemenu.add_separator()
        filemenu.add_command(label="Exit", command=root.quit)

        helpmenu = tk.Menu(menubar, tearoff=0)
        helpmenu.add_command(label="About...", command=donothing)

        root.config(menu=menubar)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)

        # Create the panes and frames
        vertical_pane = ttk.PanedWindow(self.root, orient=VERTICAL)
        vertical_pane.grid(row=0, column=0, sticky="nsew")
        #vertical_pane.grid(row=1, column=1, sticky="nsew")
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
        #self.third.labelText = 'OCF/*/oic%2Fd/R'
        self.root.protocol('WM_DELETE_WINDOW', self.quit)
        self.root.bind('<Control-q>', self.quit)
        signal.signal(signal.SIGINT, self.quit)

    def quit(self, *args):
        """ quit function for the app
        """
        # unsubscribe from the topic
        self.client.unsubscribe(self.subscribe_topic)
        self.client.loop_stop()
        self.client.disconnect()
        self.root.destroy()


def random_string():
    """create random uuid
    Returns:
        string: random uuid
    """
    x = uuid.uuid1()
    return str(x)

app = None

def config_init(config, file):
    'Create a configuration file if does not exist'
    config.add_section('MQTT')
    config.set('MQTT', 'host', '192.168.178.89')
    config.set('MQTT', 'port', 1883)
    config.set('MQTT', 'client_id', uuid.uuid1())
    config.set('MQTT', 'keepalive', 5)
    config.add_section('Security')
    config.set('Security', 'username', 'my_username')
    config.set('Security', 'password', 'my_password')
    config.set('Security', 'cert', 'my_cert')
    with open(file, 'w') as output:
        config.write(output)

def donothing():
   filewin = tk.Toplevel(app.root)
   button = tk.Button(filewin, text="Do nothing button")
   button.pack()


def main():
    # commandline arguments to the application, so that the app is quite generic to use.
    parser = argparse.ArgumentParser()
    parser.add_argument('-H', '--host', required=False,
                        default="192.168.178.89", help="The host name or ip address of the MQTT server")
    parser.add_argument('-c', '--clientid', required=False, default=None, help="The MQTT client id")
    parser.add_argument('-u', '--username', required=False, default=None)
    #parser.add_argument('-d', '--disable-clean-session', action='store_true', help="disable 'clean session' (sub + msgs not cleared when client disconnects)")
    parser.add_argument('-p', '--password', required=False, default=None)
    parser.add_argument('-wc', '--writeconfig', required=False, default=None, action='store_true',help="writes an example config file")
    parser.add_argument('-rc', '--readconfig', required=False, default=None, help="Reads the configuration file with a specific filename")
    parser.add_argument('-P', '--port', required=False, type=int,
                        default=None, help='Defaults to 8883 for TLS or 1883 for non-TLS')
    parser.add_argument('-k', '--keepalive',
                        required=False, type=int, default=60, help="The keep alive interval in seconds.")
    parser.add_argument('-s', '--use-tls', action='store_true')
    parser.add_argument('--insecure', action='store_true')
    parser.add_argument('-F', '--cacerts', required=False, default=None, help="the certificate file name")
    parser.add_argument('--tls-version', required=False, default=None,
                        help='TLS protocol version, can be one of tlsv1.2 tlsv1.1 or tlsv1\n')

    print("===============")
    args, unknown = parser.parse_known_args()

    config = configparser.RawConfigParser()
    if  os.path.exists('mqtt.config'):
        config.read('mqtt.config')
    elif args.readconfig is not None:
       if  os.path.exists(args.readconfig ):
         config.read(args.readconfig )
         print("Reading config file ", args.readconfig)
    else:
       config = None

    if args.writeconfig is not None:
        print ("writing config...")
        config = configparser.RawConfigParser()
        config_init(config, "mqtt.config")
        print ("writing config...done ")
        quit()

    logging.basicConfig(level=logging.DEBUG)

    #
    #  handle arguments, do this as default
    #
    broker = args.host
    if args.clientid == None:
        client_id = random_string()
        if config is None:
          print("RANDOM Client_id :", client_id)
    else:
        client_id = args.clientid
    port = args.port 
    usetls = args.use_tls   
    cacerts = None
    if port is None:
        if usetls:
            port = 8883
        else:
            port = 1883
    keep_alive = args.keepalive
    if config is not None:
        print ("  Reading Config file:")
        broker = config['MQTT']['host']
        if config.has_option('MQTT','port'):
            port = int(config['MQTT']['port'])
        if config.has_option('MQTT','client_id'):
            client_id = config['MQTT']['client_id']
        if config.has_option('MQTT','keepalive'):
            keep_alive = int( config['MQTT']['keepalive'])
        if config.has_option('Security','cacerts'):
            cacerts = config['Security']['cacerts']
            usetls = 1

    print("  Broker/Host :", broker)
    print("  Client_id   :", client_id)
    print("  port        :", port)
    print("  keep_alive  :", keep_alive)

    # create the client
    client = mqtt.Client(client_id, protocol=mqtt.MQTTv5) #, clean_session = not args.disable_clean_session)

    if usetls and config is None:
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
    elif usetls and config:
        tlsVersion = None
        cert_required = ssl.CERT_REQUIRED
        # setting tls connection
        if cacerts is not None:
            print ("Setting TLS connection with certificate:", cacerts)
            client.tls_set(ca_certs=cacerts, certfile=None, keyfile=None, cert_reqs=cert_required, tls_version=tlsVersion)

    if args.username or args.password:
       client.username_pw_set(args.username, args.password)

    # set all the callbacks
    client.on_connect = on_connect
    client.on_message = on_message
    client.on_unsubscribe = on_unsubscribe
    client.on_disconnect = on_disconnect
    # connect the client, with supplied info
    client.connect(broker, port, keep_alive)
    client.loop_start()

    # initalize the GUI application
    global app
    root = tk.Tk()
    app = App(root)

    #add the mqtt client as variable
    app.client = client

    app.root.title('OCF MQTT Spy [client_id]: '+ client_id)
    app.third.return_topic.set(client_id)
    #app.third.labelText = client_id

    # create my_udn in the mqtt client
    # used as client_id
    # used as return topic
    client.my_udn = client_id

    logger.log(logging.INFO, "broker :"+broker+"  port:"+str(port))
    logger.log(logging.INFO, "clientid :"+str(client_id))
    if args.username or args.password:
      logger.log(logging.INFO, "userid :"+str(args.username)+" password :"+str(args.password))

    # subscribe to the "multicast" topic
    app.subscribe_topic = "OCF/*/#"
    logger.log(logging.INFO, "Subscribing to topic: " + str(app.subscribe_topic))
    my_val = client.subscribe(app.subscribe_topic, 2)
    print("subscription succeeded:", my_val)

    # subscribe to the return topic
    logger.log(logging.INFO, "Subscribing to return topic: "+ str(app.client.my_udn))
    my_val = client.subscribe(app.client.my_udn, 2)
    print("subscription succeeded:", my_val)

    #app.root.config(menu=menubar)
    app.root.mainloop()


if __name__ == '__main__':
    main()
