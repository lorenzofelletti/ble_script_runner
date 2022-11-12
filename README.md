# Ble Script Runner
This Python application acts as a BLE Central that connects to devices exposing the UUID `0000ffe0-0000-1000-8000-00805f9b34fb` and exposing the characteristic `0000ffe1-0000-1000-8000-00805f9b34fb`. It then subscribes to notifications from the characteristic and, on receiving a notification, executes the script contained in the notification.

The role of the BLE peripheral is played by the Android application [BleSimpleApp](https://github.com/lorenzofelletti/SimpleBleApp). Through this app, the user can control which script to execute on the BLE Central by sending a notification to it.

## Install The Python Application
To install the application, clone the repository, `cd` to the clone directory and run the following commands:
```Bash
cd BleCentral/
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

> Note: `pyobjc` is only required on macOS, on other platforms the dependecy can be removed from `requirements.txt`, but other dependencies may be required.

Now you are ready to run the Python application on your device.

## Run The Python Application
Inside the `BleCentral` directory, and with the virtual environment activated, run:
```Bash
python main.py
```
