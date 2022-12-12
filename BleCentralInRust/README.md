# BleCentralInRust
Rust implementation of BLE Central. This is a work in progress.
At the moment, it is only tested on macOS, and it presents several limitations versus its Python counterpart:
* it does not handle peripherals disconnecting
* it does not searches continuously for peripherals
* it does not have command line arguments to specify options
* scripts must be specified with their platform-specific extension (e.g. .sh for macOS, .ps1 for Windows)
* windows powershell scripts support is untested.

Nevertheless, it is a good starting point for a Rust implementation of BLE Central, and works pretty well as long as the peripheral does not disconnect.
