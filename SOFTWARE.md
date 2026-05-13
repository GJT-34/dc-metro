# Installing the Software

1. Connect the MatrixPanel to your computer using a USB-C cable. Double click the button on the board labeled _RESET_. The board should mount onto your computer as a storage volume, most likely named _MATRXS3BOOT_.
    
    ![Matrix Connected via USB](img/usb-connected.jpg)

2. Flash your _Matrix Portal_ with the latest release of CircuitPython 10.
- Download the current 10.X.X version of the *.uf2 firmware from Adafruit, using the proper version for the [S3](https://circuitpython.org/board/adafruit_matrixportal_s3/), depending on which _Matrix Portal_ type you're using. If CircuitPython 10 is no longer the current version, you can still find it using the links in the "Previous Versions of CircuitPython" section of the page in the prior link. Use the most recent 10.X.X. release available. 
- Drag the downloaded _.uf2_ file into the root of the _MATRXS3BOOT_ volume.
- The board will automatically flash the version of CircuitPython and remount as _CIRCUITPY_.
- If something goes wrong, refer to the [Adafruit Documentation](https://learn.adafruit.com/adafruit-matrixportal-m4/install-circuitpython). Note that the S3 has some additional installation methods compared to the M4, as shown on the page (noted above) used to download CircuitPython software for the S3.

3. Download this repository (wmata_metro_trainboard) as a ZIP file by selecting the green 'Code' button at the top of this page, selecting the "Local" tab, and selecting the "Download ZIP" link.

4. Where you have downloaded the ZIP file on your computer, decompress it. In the resulting folder will be a file called _lib.zip_. Copy this to the root of the _CIRCUITPY_ volume, and then decompress it. There should be one folder named _lib_, with multiple files in it. After the _lib_ folder is created, you can delete _lib.zip_ from the _CIRCUITPY_ volume, as it's no longer needed.

5. The ZIP file you downloaded to your computer from this repository also contains a folder called _src_. Copy all of the Python files from this folder into the root of the _CIRCUITPY_ volume. The final file structure should look like this:

    ![Source Files](img/file_manager.webp)

6. The board should now light up and say "Loading..." and then begin repeatedly trying to connect to wifi, but we've still got some work to do.

7. Obtain a WMATA API key.

- Create a WMATA developer account on [WMATA's Developer Website](https://developer.wmata.com/signup/).
- After your account is created, add the _Default Tier_ subscription to your account on [this page](https://developer.wmata.com/products/).
- After doing this, you will be redirected to [your profile](https://developer.wmata.com/profile).
- Under the _Subscriptions_ section on your profile, select the **show** button beside the _Primary Key_. This is the key that allows the board to communicate with WMATA.

8. Add needed information into the settings.toml file.

- Open the [settings.toml](src/settings.toml) file located in the root of the _CIRCUITPY_ volume.
- Fill in your wifi SSID and password and WMATA API key.
- Save this file.
  
If everything has gone successfully, after a couple second pause your board should connect to wifi and begin displaying data. We still need to edit the configuration so it shows the right data, though. That's the next step.

Next: ![Editing the configuration file](https://github.com/GJT-34/wmata_metro_trainboard/blob/main/CONFIGURE.md)
