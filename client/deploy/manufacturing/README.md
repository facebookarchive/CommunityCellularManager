# Enaga Client setup

Think of this as the steps the factory does to manufacture a CCM system.

## Hardware/BIOS preparation

### Jetway JBC373F38W-525 (The “Atom box”)

* Go to BIOS (press “delete” when starting) and make the following changes
    * Integrated Peripherals > Onboard SATA function > Onboard SATA as: Change to “AHCI”.
    * Power Management Setup > ERP Function: Disabled
    * Power Management Setup > PWR Status after PWR Failure > Always On
        * This only shows up after you disable ERP
    * Save & Exit Setup

## System provisioning

### Creating a preseeded image

1. Download an official Debian 8 image and put it on a USB stick using UNetbootin. When you're done, mount the newly-created disk.
2. Download the Realtek non-free firmware from [here](http://cdimage.debian.org/cdimage/unofficial/non-free/firmware/jessie/current/firmware.zip) (it's `firmware-realtek_$VERSION.deb`). Put it on the USB disk under `/firmware`.
3. Copy the following files from `release/manufacturing` to the specified location on the USB stick:
    1. `ccm.seed` → `/preseed/cmm.seed`
    2. `syslinux.cfg` → `/syslinux.cfg`
    3. `setup_ccm.sh` → `/preseed/setup_ccm.sh` (this is the post-imaging setup script)
    4. `../../deploy/files/endaga-preferences` → `/preseed/endaga-preferences`
    5. `../../deploy/files/osmocom-preferences` → `/preseed/osmocom-preferences`
    7. You can also directly modify the existing `syslinux.cfg` on the USB stick. The important bits are:
        1. `timeout 1`, so it'll boot quickly and automatically
        2. Delete all boot configuration sections except the default one
        3. Add .... to the append line to pass this into the boot configuration.
    8. **The above compressed into two commands (assuming you're already in `release/manufacturing` and the boot disk is mounted at `$MOUNT_DIR`):**
        1. `cp ccm.seed setup_ccm.sh ../../deploy/files/endaga-preferences ../../deploy/files/osmocom-preferences $MOUNT_DIR/preseed`
        2. `cp syslinux.cfg $MOUNT_DIR`

### SAVING THE IMAGE

1. If you want to save the image you've created for easy future use, you can take a raw disk image.
2. Figure out what device your USB disk is; for me, it was `/dev/sdb`. This might not be the case for you — change if needed.
3. MAKE ABSOLUTELY SURE THAT YOU UNDERSTAND THIS COMMAND. MISTAKES CAN OVERWRITE YOUR HARD DRIVE.
4. Similarly update the date and debian base version as appropriate.
5. Run (on Linux): `dd if=/dev/<your USB device> bs=8M | gzip -c > 2017jan19.debian.8.7.1.amd64.tar.gz`
    1. Script:

        `dd if=/dev/<your USB device> bs=8M | gzip -c > $(date +%Y%b%d | awk '{ print tolower($0) }')`.debian.8.7.1.amd64.tar.gz``
6. You can add this to Dropbox to share with others.

### installing on the box

1. Prepare the install media (a USB stick) so that it's a pre-seeded install disk.
    1. You can go through the “Creating a Preseeded Image” steps, and after step 3 you'll have a usable, bootable USB stick. You can just use that here.
    2. Alternatively, you can write a pre-seeded binary image to a USB key and use that.
        1. MAKE ABSOLUTELY SURE THAT YOU UNDERSTAND THIS COMMAND. MISTAKES CAN OVERWRITE YOUR HARD DRIVE.
        2. Figure out what device your USB disk is; for me, it was `/dev/sdb`. This command assumes your image is in your current working directory and is called `2017jan19.debian.8.7.1.amd64.tar.gz`. Update the command as appropriate.
        3. Run (on Linux): `zcat 2017jan19.debian.8.7.1.amd64.tar.gz | sudo dd of=/dev/<your USB device> bs=8M`
2. Plug the prepared USB stick into the prepared hardware (follow the steps for your model in “Hardware/BIOS preparation”).
3. If necessary, change the boot order so you boot from the USB stick first.
4. Ensure the device is connected to a network that provides an address via DHCP and has Internet connectivity.
5. Let the installation process complete. This could take a while.
6. Once installation is complete, the machine may reboot, or you could see an error or a weird menu. Just ignore that and restart the machine. Don't forget to remove the USB stick!
7. `endaga-osmocom` is not installed at this point! When the machine reboots, login then run `sudo apt-get update; sudo apt-get install -y endaga-osmocom; sudo reboot`
8. Point the client to the cloud instance `endaga_db_set registry https://<CLOUD_SERVER>/api/v1`
9. Add the tower `snowflake` on the cloud towers dashboard https://<CLOUD_SERVER>/dashboard/towers
10. Configure the BSC external interface to the interface matching the VPN (typically the interface with an address in 10.64.1.0/20) `endaga_db_set external_interface tun1`
11. Configure the BSC internal interface to the one the BTS is connected to (use lo if using osmo-bts-trx) `endaga_db_set internal_interface eth0`
12. Configure osmo-sip-connector `remote` config at /etc/osmocom/osmo-sip-connector.cfg to the IP of the BTS that is exposed on the internal interface (use 127.0.0.1 if using osmo-bts-trx) 
13. Configure the BTS to use the BSC (don't need to change anything if using osmo-bts-trx)
    1. Set `oml remote-ip` to the address of the BSC
    2. Set the `ipa unit-id` to 1800 to match what is defined in BSC configs
14. Restart the BTS and `sudo reboot` the BSC
15. Validate the BTS is connected to the BSC in the NITB vty `telnet 127.0.0.1 4242` and `show bts <BTS_ID>`

