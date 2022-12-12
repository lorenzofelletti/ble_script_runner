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

/// Only devices whose services contains this UUID will be tried.
const PERIPHERAL_SERVICE_UUID: Uuid = Uuid::from_u128(0x0000ffe0_0000_1000_8000_00805f9b34fb);
/// UUID of the characteristic for which we should subscribe to notifications.
const SCRIPT_CHARACTERISTIC_UUID: Uuid = Uuid::from_u128(0x0000ffe1_0000_1000_8000_00805f9b34fb);
/// UUID of the characteristic to update the peripheral on the script's execution status.
/// This is optional, and if not present, the script will be executed without any feedback.
const STATUS_CHARACTERISTIC_UUID: Uuid = Uuid::from_u128(0x0000ffe2_0000_1000_8000_00805f9b34fb);

/// UUID of a non-existent characteristic.
/// This is used to return a characteristic when we cannot find the one we are looking for.
const NON_EXISTENT_CHARACTERISTIC_UUID: Uuid =
    Uuid::from_u128(0x00000000_0000_0000_0000_000000000000);

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

/// Filter the characteristics to only keep the ones that have the given UUIDs.
///
/// # Arguments
/// * `characteristics` - The characteristics to filter.
/// * `uuids` - The UUIDs to keep.
///
/// # Returns
/// * `HashMap<Uuid, Characteristic>` - The filtered characteristics.
fn filter_characteristics_by_uuids(
    characteristics: &BTreeSet<Characteristic>,
    uuids: &Vec<Uuid>,
) -> HashMap<Uuid, Characteristic> {
    let mut filtered_characteristics = HashMap::new();
    for characteristic in characteristics.iter() {
        if uuids.contains(&characteristic.uuid) {
            filtered_characteristics.insert(characteristic.uuid, characteristic.clone());
        }
    }
    filtered_characteristics
}

/// Get the script and status characteristics from the given characteristics. if they are present.
/// If they are not present, the [NON_EXISTENT_CHARACTERISTIC] will be returned.
///
/// # Arguments
/// * `characteristics` - The characteristics to filter.
///
/// # Returns
/// * `(Characteristic, Characteristic)` - The script and status characteristics, respectively.
fn get_script_and_status_characteristics_if_present(
    characteristics: &BTreeSet<Characteristic>,
) -> (Characteristic, Characteristic) {
    let uuids = vec![SCRIPT_CHARACTERISTIC_UUID, STATUS_CHARACTERISTIC_UUID];
    let filtered_characteristics = filter_characteristics_by_uuids(characteristics, &uuids);

    let script_characteristic = filtered_characteristics
        .get(&SCRIPT_CHARACTERISTIC_UUID)
        .unwrap_or(&NON_EXISTENT_CHARACTERISTIC)
        .clone();

    let status_characteristic = filtered_characteristics
        .get(&STATUS_CHARACTERISTIC_UUID)
        .unwrap_or(&NON_EXISTENT_CHARACTERISTIC)
        .clone();

    (script_characteristic, status_characteristic)
}

fn script_characteristic_present_and_notifiable(script_characteristic: &Characteristic) -> bool {
    script_characteristic.uuid != NON_EXISTENT_CHARACTERISTIC_UUID
        && script_characteristic
            .properties
            .contains(CharPropFlags::NOTIFY)
}

/// Takes the data from the notification and return the script to execute.
///
/// # Arguments
/// * `data` - The data received from the notification.
///
/// # Returns
/// * `Result<String, Box<dyn Error>>` - The script to execute.
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

/// Execute a script and return the exit code.
///
/// It will also print the output of the script to the console.
///
/// # Arguments
/// * `script` - The script to execute, optionally with arguments.
///
/// # Returns
/// * `i32` - The exit code of the script.
fn run_script(script: &String) -> i32 {
    println!("Running script {:?}", script);

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

/// Discover peripheral services and return `true` if the peripheral has the given service, `false` otherwise.
async fn peripheral_has_service(
    peripheral: &btleplug::platform::Peripheral,
    service_uuid: Uuid,
) -> bool {
    let service_discovery_result = peripheral.discover_services().await;

    if service_discovery_result.is_err() {
        return false;
    }

    let services = peripheral.services();

    for service in services {
        if service.uuid == service_uuid {
            return true;
        }
    }
    false
}

/// Scan for peripherals using the given adapter, and return the list of peripherals or an empty vector.
/// This function will scan for peripherals for a fixed amount of time.
///
/// # Arguments
/// * `adaper` - The adapter to use for scanning.
/// * `scan_filter` - The filter to use for scanning, or `None` to use the default filter.
///
/// # Returns
/// * `Vec<btleplug::platform::Peripheral>` - The list of peripherals found.
async fn scan(
    adaper: &btleplug::platform::Adapter,
    scan_filter: Option<&ScanFilter>,
) -> Vec<btleplug::platform::Peripheral> {
    let default_filter = &ScanFilter::default();
    let scan_filter = scan_filter.unwrap_or(default_filter);

    adaper
        .start_scan(scan_filter.to_owned())
        .await
        .expect("Can't scan BLE adapter for connected devices...");

    time::sleep(SCAN_FOR_PERIPHERALS_TIMEOUT).await;

    // unwrap peripherals or empty vector
    adaper.peripherals().await.unwrap_or(vec![])
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    pretty_env_logger::init();

    let manager = Manager::new().await?;
    let adapter_list = manager.adapters().await?;
    if adapter_list.is_empty() {
        eprintln!("No Bluetooth adapters found");
    }

    // create a scan filter to only scan for devices with the given service UUID
    let mut scan_filter = ScanFilter::default();
    scan_filter.services = vec![PERIPHERAL_SERVICE_UUID];

    for adapter in adapter_list.iter() {
        println!("Starting scan...");
        let peripherals = scan(adapter, Some(&scan_filter)).await;

        if peripherals.is_empty() {
            eprintln!("->>> BLE peripheral devices were not found, sorry. Exiting...");
            continue;
        }

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

            // Connect if we aren't already connected.
            if !is_connected {
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

            let found_service = peripheral_has_service(peripheral, PERIPHERAL_SERVICE_UUID).await;

            if found_service {
                // get script and status characteristics, using get_script_and_status_characteristics_if_present
                let (script_characteristic, status_characteristic) =
                    get_script_and_status_characteristics_if_present(&peripheral.characteristics());

                match script_characteristic_present_and_notifiable(&script_characteristic) {
                    false => {
                        println!(
                            "->>> Script characteristic not found or not notifyable, skipping..."
                        );
                    }
                    true => {
                        println!(
                            "Subscribing to characteristic {:?}",
                            script_characteristic.uuid
                        );
                        peripheral.subscribe(&script_characteristic).await?;

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
                            if status_characteristic != NON_EXISTENT_CHARACTERISTIC {
                                peripheral.read(&status_characteristic).await?;
                            }

                            // Execute the script.
                            let exit_code = run_script(&cmd_string);

                            // Inform the peripheral that we have finished executing the script.
                            if status_characteristic != NON_EXISTENT_CHARACTERISTIC {
                                let data = exit_code.to_string().as_bytes().to_vec();

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
                };
            }
            println!("Disconnecting from peripheral {:?}...", local_name);
            peripheral.disconnect().await?;
        }
    }
    Ok(())
}
