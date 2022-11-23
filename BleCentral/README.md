# Ble Script Runner
This Python application acts as a BLE Central that connects to peripheral devices exposing the service UUID `0000ffe0-0000-1000-8000-00805f9b34fb`.
Such devices are expected to expose the characteristics `0000ffe1-0000-1000-8000-00805f9b34fb`, and `0000ffe2-0000-1000-8000-00805f9b34fb`. The application subscribes to notifications from the former and, on receiving a notification, executes the script contained in the notification. The latter is used to send the result of the script execution back to the BLE peripheral device.

> Note: An implementation of such a BLE peripheral is provided by the Android application [BleSimpleApp](https://github.com/lorenzofelletti/SimpleBleApp). Through this app, the user can control which script to execute on the BLE Central by sending a notification to it.

## Install The Python Application
To install the application, run the following commands (inside the `BleCentral` directory):
```Bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements_[your_os].txt
```

> Note: Replace source `venv/bin/activate` with `venv\Scripts\activate` on Windows.

> Note: there are different requirements files for different operating systems. The one to use is specified in the file name, e.g. `requirements_macos.txt` for macOS.

Now you are ready to run the Python application.

## Run The Python Application
Inside the `BleCentral` directory, and with the virtual environment activated, run:
```Bash
python main.py
```
