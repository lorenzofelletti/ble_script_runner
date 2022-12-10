use btleplug::api::{
    Central, CharPropFlags, Characteristic, Manager as _, Peripheral, ScanFilter, WriteType,
};
use btleplug::platform::Manager;
use futures::stream::StreamExt;
use std::collections::{BTreeSet, HashMap};
use std::error::Error;
use std::path::Path;
use std::time::Duration;
use tokio::time;
use uuid::Uuid;

/// Whitelist of devices names.
/// This is a list of devices that we want to connect to.
const DEVICES_NAMES_WHITELIST: [&str; 1] = ["Pixel 3a"];

/// Only devices whose services contains this UUID will be tried.
const PERIPHERAL_SERVICE_UUID: Uuid = Uuid::from_u128(0x0000ffe0_0000_1000_8000_00805f9b34fb);
/// UUID of the characteristic for which we should subscribe to notifications.
const SCRIPT_CHARACTERISTIC_UUID: Uuid = Uuid::from_u128(0x0000ffe1_0000_1000_8000_00805f9b34fb);
/// UUID of the characteristic to update the peripheral on the script's execution status.
/// This is optional, and if not present, the script will be executed without any feedback.
const STATUS_CHARACTERISTIC_UUID: Uuid = Uuid::from_u128(0x0000ffe2_0000_1000_8000_00805f9b34fb);

const NON_EXISTENT_CHARACTERISTIC_UUID: Uuid =
    Uuid::from_u128(0x00000000_0000_1000_8000_000000000000);

const NON_EXISTENT_CHARACTERISTIC: Characteristic = Characteristic {
    uuid: NON_EXISTENT_CHARACTERISTIC_UUID,
    service_uuid: NON_EXISTENT_CHARACTERISTIC_UUID,
    properties: CharPropFlags::empty(),
};

const SCAN_FOR_PERIPHERALS_TIMEOUT: Duration = Duration::from_secs(3);

/// Returns the current working directory.
fn get_current_working_dir() -> Result<String, Box<dyn Error>> {
    let path = std::env::current_dir()?;
    Ok(path.to_str().unwrap().to_string())
}

fn search_characteristics_with_uuid(
    characteristics: &BTreeSet<Characteristic>,
    uuids: &[Uuid],
) -> HashMap<Uuid, Characteristic> {
    let mut filtered_characteristics = HashMap::new();
    for characteristic in characteristics.iter() {
        if uuids.contains(&characteristic.uuid) {
            filtered_characteristics.insert(characteristic.uuid, characteristic.clone());
        }
    }
    filtered_characteristics
}

/**
 * Takes the data from the notification and return the script to execute.
 */
fn get_script_to_execute_from_data(data: &[u8]) -> Result<String, Box<dyn Error>> {
    if data.len() == 0 {
        return Err("No data received".into());
    }
    let data = String::from_utf8(data.to_vec())?;

    let current_dir = get_current_working_dir()?;

    let script = Path::new(&data);

    // prepend scripts directory
    let path = Path::new(&current_dir).join("scripts").join(script);

    Ok(path.to_str().unwrap().to_string())
}

/**
 * Execute a script and return the output.
 */
fn run_script(script: &String) -> i32 {
    println!("AAAAARunning script {:?}", script);

    let parsed_script_and_args = shell_words::split(script).unwrap();

    let join_handle = std::thread::spawn(move || {
        // Preparing command and arguments
        let command_name = parsed_script_and_args[0].clone();
        let args = &parsed_script_and_args[1..];

        // Running command
        let output = std::process::Command::new(&command_name)
            .args(args)
            .output()
            .expect("failed to execute process");

        // Returning output
        output
    });

    let output = join_handle.join();

    // Returning exit code, printing output if any
    match output {
        Ok(output) => {
            println!("Output: {:?}", String::from_utf8_lossy(&output.stdout));
            output.status.code().unwrap_or(255)
        }
        Err(_) => 255,
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    pretty_env_logger::init();

    let manager = Manager::new().await?;
    let adapter_list = manager.adapters().await?;
    if adapter_list.is_empty() {
        eprintln!("No Bluetooth adapters found");
    }

    for adapter in adapter_list.iter() {
        println!("Starting scan...");
        adapter
            .start_scan(ScanFilter::default())
            .await
            .expect("Can't scan BLE adapter for connected devices...");
        time::sleep(SCAN_FOR_PERIPHERALS_TIMEOUT).await;
        let peripherals = adapter.peripherals().await?;

        if peripherals.is_empty() {
            eprintln!("->>> BLE peripheral devices were not found, sorry. Exiting...");
        } else {
            // All peripheral devices in range.
            for peripheral in peripherals.iter() {
                let properties = peripheral.properties().await?;
                let is_connected = peripheral.is_connected().await?;
                let local_name = properties
                    .unwrap()
                    .local_name
                    .unwrap_or(String::from("(peripheral name unknown)"));
                println!(
                    "Peripheral {:?} is connected: {:?}",
                    &local_name, is_connected
                );

                if !DEVICES_NAMES_WHITELIST.iter().any(|&x| x == local_name) {
                    println!(
                        "Skipping device {:?} because it's not in the whitelist",
                        local_name
                    );
                    continue;
                }

                if !is_connected {
                    // Connect if we aren't already connected.
                    if let Err(err) = peripheral.connect().await {
                        eprintln!("Error connecting to peripheral, skipping: {}", err);
                        continue;
                    }
                }
                let is_connected = peripheral.is_connected().await?;
                println!(
                    "Now connected ({:?}) to peripheral {:?}...",
                    is_connected, &local_name
                );
                peripheral.discover_services().await?;
                let services = peripheral.services();
                let mut found_service = false;
                if services.is_empty() {
                    eprintln!(
                        "->>> No services found for peripheral device: {:?}",
                        peripheral.address()
                    );
                } else {
                    // All services for the current peripheral device.
                    for service in services.iter() {
                        if service.uuid == PERIPHERAL_SERVICE_UUID {
                            println!("->>> Found service: {:?}", service);
                            found_service = true;
                            break;
                        }
                    }
                }
                if found_service {
                    let characteristics = peripheral.characteristics();

                    let searched_characteristics = search_characteristics_with_uuid(
                        &characteristics,
                        &vec![STATUS_CHARACTERISTIC_UUID, SCRIPT_CHARACTERISTIC_UUID],
                    );

                    let script_characteristic = searched_characteristics
                        .get(&SCRIPT_CHARACTERISTIC_UUID)
                        .unwrap_or(&NON_EXISTENT_CHARACTERISTIC);
                    let status_characteristic = searched_characteristics
                        .get(&STATUS_CHARACTERISTIC_UUID)
                        .unwrap_or(&NON_EXISTENT_CHARACTERISTIC);

                    if script_characteristic == &NON_EXISTENT_CHARACTERISTIC
                        || !script_characteristic
                            .properties
                            .contains(CharPropFlags::NOTIFY)
                    {
                        println!(
                            "->>> Script characteristic not found or not notifyable, skipping..."
                        );
                    } else {
                        println!(
                            "Subscribing to characteristic {:?}",
                            script_characteristic.uuid
                        );
                        peripheral.subscribe(&script_characteristic).await?;
                        // Print the first 4 notifications received.
                        let mut notification_stream = peripheral.notifications().await?;
                        // Process while the BLE connection is not broken or stopped.
                        while let Some(data) = notification_stream.next().await {
                            println!(
                                "Received data from {:?} [{:?}]: {:?}",
                                local_name, data.uuid, data.value
                            );
                            //let value_str = String::from_utf8(data.value)?;
                            let cmd_string = get_script_to_execute_from_data(&data.value)?;

                            // Inform the peripheral that we are about to execute the script.
                            if *status_characteristic != NON_EXISTENT_CHARACTERISTIC {
                                peripheral.read(&status_characteristic).await?;
                            }

                            // Execute the script.
                            let exit_code = run_script(&cmd_string);

                            // Inform the peripheral that we have finished executing the script.
                            if *status_characteristic != NON_EXISTENT_CHARACTERISTIC {
                                let data = exit_code.to_string().as_bytes().to_vec();

                                println!(
                                    "Writing to characteristic {:?} value {:?}",
                                    status_characteristic.uuid, data
                                );

                                peripheral
                                    .write(
                                        &status_characteristic,
                                        &data,
                                        WriteType::WithoutResponse,
                                    )
                                    .await?;
                            }
                        }
                    }
                }
                println!("Disconnecting from peripheral {:?}...", local_name);
                peripheral.disconnect().await?;
            }
        }
    }
    Ok(())
}
