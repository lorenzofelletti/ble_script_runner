# Ble Script Runner
This repository contains the code to implement a Bluetooth LE Central and Peripheral that communicate with each other to execute scripts on the Central.

The BLE Central is a Python application that connects to peripheral devices exposing the service UUID `0000ffe0-0000-1000-8000-00805f9b34fb`. Such devices are expected to expose the characteristics `0000ffe1-0000-1000-8000-00805f9b34fb`, and `0000ffe2-0000-1000-8000-00805f9b34fb`. The application subscribes to notifications from the former and, on receiving a notification, executes the script contained in the notification. The latter is used to send the result of the script execution back to the BLE peripheral device.

The BLE Peripheral consists of an Android application that exposes the service and characteristics described above. Through this app, the user can control which script to execute on the BLE Central by sending a notification to it.

This repository is the result of the work done as Project Work in the course of Mobile Systems at the University of Bologna, during the academic year 2021/2022.

A detailed description of the project can be found in the [project report](Project_Work_In_Mobile_Systems.pdf).
