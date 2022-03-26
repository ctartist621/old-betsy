import os
import zipfile

import requests

for file_name in range(20220101, 20220201):
    print(f"Retrieving {file_name}")
    resp = requests.get(f"http://reversebeacon.net/raw_data/dl.php?f={file_name}")

    zip_file = f"data/{file_name}.zip"
    f = open(zip_file, mode="wb")
    f.write(resp.content)
    f.close()

    try:
        with zipfile.ZipFile(zip_file) as z:
            with open(f"data/reverse_beacon_network/{file_name}.csv", mode="w") as f:
                f.write(z.read(f"{file_name}.csv").decode("ascii"))
                print("Extracted", f"{file_name}.csv")

    except:
        print("Invalid file")

    os.remove(zip_file)
