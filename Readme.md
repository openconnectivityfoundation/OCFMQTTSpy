
# OCFMQTTSpy

Python based tool (GUI) to that communicates OCF over MQTT.
There must be an OCF-MQTT devices on the MQTT network.
<!-- TOC -->

- [OCFMQTTSpy](#ocfmqttspy)
- [Usage](#usage)
- [Install](#install)
- [Config file](#config-file)
  - [example config files](#example-config-files)

# Usage

in src folder execute: ``python ocfmqttspy.py``

use -h to see all the options.

# Install

Installation of OCFMQTTSpy is making a clone of the repository and use the tool relative of where the repository is located on your system.
To install the dependencies:

run pip3 install -U -r requirements.txt to install the dependencies.

# Config file

The default config file is "mqtt.config". A specific config file can be loaded with option -rc.

Config file will read the configuration data for:
MQTT:

- Host the host name or ip address of the MQTT server
- port, server port to be used
- client_id, the client id, not set then a random uuid will be generated
- keepalive, the keep alive for the TCP/TLS connection

Security:

- cacerts, the file name of the certificate file.

The config file is read from the same location as the python script.

An example configuration file can be generated by:
``python3 ocfmqttspy.py --writeconfig ``

## example config files

- local.config
  - example config file to connect unsecurely to a local server at 192.168.178.89
- mosquitto.config
  - example config file to connect unsecurely to a internet server at test.mosquitto.org
- mosquitto_cert.config
  - example config file to connect securely with certificate to a internet server at test.mosquitto.org

see for more info:
https://test.mosquitto.org/