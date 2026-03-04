# Yandex Music to YouTube Music Transfer

A utility for automated transfer of saved track libraries from Yandex Music to YouTube Music.

[![Build Executables (Win & Linux)](https://github.com/kordmtal/yandex2ytmusic/actions/workflows/main.yml/badge.svg?branch=improvements)](https://github.com/kordmtal/yandex2ytmusic/actions/workflows/main.yml)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
[![License](https://img.shields.io/badge/license-MIT-weight)](LICENSE)

## Execution

### Windows
1. Download the `yandex2ytmusic.exe` file from the [latest release](../../releases).
2. Run `yandex2ytmusic.exe`.
*(Note: Windows SmartScreen filter may warn about an unknown publisher. Click "More info" → "Run anyway" to launch).*

### Linux (Ubuntu)
1. Download the `yandex2ytmusic` binary from the [latest release](../../releases).
2. Open a terminal in the directory with the file, grant execution permissions, and run the utility:
   ```bash
   chmod +x yandex2ytmusic
   ./yandex2ytmusic
   ```

---

## Running from Source Code (Linux / Ubuntu)

Instructions for developers who wish to run the script directly using the Python interpreter.

```bash
# Clone the repository
git clone https://github.com/kirillqa17/yandex2ytmusic.git
cd yandex2ytmusic

# Install Python dependencies
pip3 install -r requirements.txt

# Install Playwright and system browser libraries
pip3 install playwright
playwright install-deps
playwright install chromium

# Run the application
python3 main.py
```

---

## Usage Instructions

The transfer process is divided into several independent stages to prevent data loss and session expiration.

### Step 1. Obtaining Yandex Music Token

To allow the program to read your "Liked tracks" list, you need to obtain a temporary access key (token).

1. Follow the link: [Get Yandex Token](https://oauth.yandex.ru/authorize?response_type=token&client_id=23cabbbdc6cd418abb4b39c32c41195d).
2. Log in to your Yandex account and confirm access.
3. After confirmation, you will be redirected to the **Yandex Music** home page.
4. At this point, look at the **browser's address bar**. It will contain your token and look like this:
   `https://music.yandex.ru/#access_token=`**`y0_AgAAAABp...`**`&token_type=bearer&expires_in=...`
5. You need to copy only the token itself — the long string of characters located **after** `access_token=` and **before** the `&` symbol.

**Example:**
> If the browser bar shows: `...#access_token=`**`AQAAAAA...`**`&token_type=...`  
> Copy only: **`AQAAAAA...`**

6. Paste this token into the program when selecting **option 2** in the main menu.

> **Important:** The token provides temporary access to your data. Do not publish it openly or share it with third parties.

### Step 2. Exporting from Yandex Music
1. Run the utility and select menu option `2` (Export from Yandex Music only).
2. Paste the copied token.
3. Wait for the process to complete. The program will create a `tracks.json` file in the current directory, containing a list of all your saved tracks.

### Step 3. Setting up YouTube Music Authentication

To interact with your YouTube Music account, you must provide authentication data to the utility. **The manual method is the most reliable way.**

1. Run the utility and select menu option `4` (Setup YouTube Music authentication), then choose option `2` (Manual).
2. Open the Firefox browser and go to [music.youtube.com](https://music.youtube.com). Make sure you are logged into your Google account.
3. Open Developer Tools (**F12** or **Ctrl+Shift+I**).
4. Go to the **Network** tab.
5. In the filter field, type `browse`.
6. Refresh the page or perform any action on the site (e.g., click the YouTube Music logo) to make the request appear in the list.
7. Find a row named `browse?...` where the **Method** column says **POST**.
8. Right-click on this request and copy the request headers:
   - **In Firefox:** Copy Value → Copy Request Headers.
9. Return to the terminal window with the running program.
10. Paste the copied headers.
11. To finish the input, press:
    - **On Windows:** `Ctrl+Z`, then `Enter`.
    - **On Linux:** `Ctrl+D`.

After these steps, the program will create a `browser.json` file, which will be used for subsequent track imports.

### Step 4. Importing Tracks
1. Select menu option `3` (Import to YouTube Music only) in the main menu.
2. The utility will ask you to choose an import mode:
   ### ATTENTION: During parallel import of more than 100 tracks, YouTube may fail to save some likes!
   * **Fast (parallel):** tracks are added using multiple threads. The order of tracks in the resulting playlist is not guaranteed.
   * **Keep order:** tracks are added sequentially. The playlist in YouTube Music will fully correspond to the order in Yandex Music.

---

## Troubleshooting

| Error / Issue | Solution |
|-------------------|---------|
| **Error 401 Unauthorized** | The YouTube session has expired. Repeat Step 3 (Authentication Setup) to update the data in `browser.json`. |
| **Tracks not transferred** | Due to regional licensing differences or naming variations, some tracks may not be found. The list of skipped tracks is available in the `tracks.json` file (`not_found` section). |
| **Browser launch error (Linux)** | Ensure that the system dependencies for Chromium are installed. When running from source code, execute the `playwright install-deps` command. |

---

## Credits and Dependencies

* Based on the source code by [@kirillqa17](https://github.com/kirillqa17).
* Yandex Music API interaction: [yandex-music-api](https://github.com/MarshalX/yandex-music-api).
* YouTube API interaction: [ytmusicapi](https://github.com/sigma67/ytmusicapi).
* Browser automation: [Playwright](https://playwright.dev/python/).

## License

This project is distributed under the MIT License. See the `LICENSE` file for details.