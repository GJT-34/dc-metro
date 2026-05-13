# Installing the Software

1. Connect the MatrixPanel to your computer using a USB-C cable. Double click the button on the board labeled _RESET_. The board should mount onto your computer as a storage volume, most likely named _MATRXS3BOOT_.
    
    ![Matrix Connected via USB](img/usb-connected.jpg)

2. Flash your _Matrix Portal_ with the latest release of CircuitPython 10.
    - Download the most recent 10.X.X version of the *.uf2 firmware from Adafruit, using the proper version for the [S3](https://circuitpython.org/board/adafruit_matrixportal_s3/), depending on which _Matrix Portal_ type you're using. If CircuitPython 10.X.X is no longer the current version, you can still find it using the links in the "Previous Versions of CircuitPython" section of the page in the prior link. Use the most recent 10.X.X. release available. 
    - Drag the downloaded _.uf2_ file into the root of the _MATRIXBOOT_ or _MATRXS3BOOT_ volume.
    - The board will automatically flash the version of CircuitPython and remount as _CIRCUITPY_.
    - If something goes wrong, refer to the [Adafruit Documentation](https://learn.adafruit.com/adafruit-matrixportal-m4/install-circuitpython). Note that the S3 has some additional installation methods compared to the M4, as shown on the page (noted above) used to download CircuitPython software for the S3.

3. Decompress the _lib.zip_ file from this repository into the root of the _CIRCUITPY_ volume. There should be one folder named _lib_, with a plethora of files underneath. You can delete _lib.zip_ from the _CIRCUITPY_ volume, as it's no longer needed.

    ![Lib Decompressed](img/lib.png)

4. Download this repository as a ZIP file by selecting the green 'Code' button at the top of this page, and then unzip the file.

5. Copy all of the Python files from the downloaded repository into the root of the _CIRCUITPY_ volume.

    ![Source Files](img/source.png)

6. The board should now light up with a loading screen, but we've still got some work to do.

    ![Loading Sign](img/bd4.jpg)

## Getting a WMATA API Key

1. Create a WMATA developer account on [WMATA's Developer Website](https://developer.wmata.com/signup/).

2. After your account is created, add the _Default Tier_ subscription to your account on [this page](https://developer.wmata.com/products/5475f1b0031f590f380924fe).

3. After doing this, you will be redirected to [your profile](https://developer.wmata.com/developer).

4. Under the _Subscriptions_ section on your profile, select the **show** button beside the _Primary Key_. This is the key that allows the board to communicate with WMATA.

## Setting Up the Board to Connect to WMATA

1. Open the [settings.toml](src/settings.toml) file located in the root of the _CIRCUITPY_ volume.

2. Fill in your wifi SSID and password and WMATA API key.

3. Save this file. At this point, your board should refresh and connect to WMATA.

Next: ![Editing the configuration file](https://github.com/GJT-34/wmata_metro_trainboard/blob/main/CONFIGURE.md)
