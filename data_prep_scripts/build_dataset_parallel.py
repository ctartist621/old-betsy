import asyncio
import os
import random
import time
from asyncio import futures

import dask
import dask.dataframe as ddf
import numpy as np
import pandas as pd
import requests
import untangle
from dask.distributed import Client, LocalCluster, as_completed
from progress.bar import Bar

username = os.getenv("HAMQTH_USERNAME")
password = os.getenv("HAMQTH_PASSWORD")
api_root = "https://www.hamqth.com/xml.php"
auth_uri = f"{api_root}?u={username}&p={password}"
data_dir = "data/hamqth"

# Get HamQTH Session ID
document = untangle.parse(auth_uri)
session_id = document.HamQTH.session.session_id.cdata
csv_file = "/Users/dave/code/old-betsy/data/full.csv"


def callsign_to_filename(callsign: str) -> str:
    keepcharacters = (" ", ".", "_")
    return "".join(c for c in callsign if c.isalnum() or c in keepcharacters).rstrip()


def get_gridsquare_for_callsign(
    spots_ddf: pd.DataFrame,
    spot,
    callsign_to_lookup: str,
    prefix: str,
) -> pd.DataFrame:
    _spots_ddf = spots_ddf
    grid = None
    lat = None
    lon = None
    if os.path.exists(f"{data_dir}/{callsign_to_filename(callsign_to_lookup)}.xml"):
        # print("Using Stored result: ", callsign_to_lookup)
        try:
            callsign_result = untangle.parse(
                f"{data_dir}/{callsign_to_filename(callsign_to_lookup)}.xml"
            )
            if hasattr(callsign_result.HamQTH, "search") and hasattr(
                callsign_result.HamQTH.search, "grid"
            ):
                grid = callsign_result.HamQTH.search.grid.cdata
            if hasattr(callsign_result.HamQTH, "search") and hasattr(
                callsign_result.HamQTH.search, "latitude"
            ):
                lat = callsign_result.HamQTH.search.latitude.cdata
            if hasattr(callsign_result.HamQTH, "search") and hasattr(
                callsign_result.HamQTH.search, "longitude"
            ):
                lon = callsign_result.HamQTH.search.longitude.cdata
        except:
            pass
    else:
        # print("Callsign not available", callsign_to_lookup)
        pass

    _spots_ddf.at[spot.Index, f"{prefix}_grid"] = grid
    _spots_ddf.at[spot.Index, f"{prefix}_lat"] = lat
    _spots_ddf.at[spot.Index, f"{prefix}_lon"] = lon

    return _spots_ddf


def join_ak(spot, ak_indices) -> pd.DataFrame:
    _spots_ddf = pd.DataFrame([spot]).set_index("Index")
    start_filter = ak_indices["start_time"].values <= spot.date
    ak_filtered = ak_indices[start_filter]

    end_filter = spot.date < ak_filtered["end_time"].values
    ak_filtered = ak_filtered[end_filter]

    _spots_ddf = get_gridsquare_for_callsign(
        _spots_ddf, spot, spot.callsign, "callsign"
    )

    _spots_ddf = get_gridsquare_for_callsign(_spots_ddf, spot, spot.dx, "dx")

    if len(ak_filtered) > 0:
        for station in ak_indices["station"].unique():
            _spots_ddf.at[spot.Index, f"{station}_A_index"] = ak_filtered[
                ak_filtered["station"] == station
            ]["A_index"].values
            _spots_ddf.at[spot.Index, f"{station}_K_index"] = ak_filtered[
                ak_filtered["station"] == station
            ]["K_index"].values

    else:
        print("Missmatched spot: ", spot)

    return _spots_ddf


if __name__ == "__main__":

    cluster = LocalCluster(processes=True)
    client = Client(cluster)
    print(client)
    if os.path.exists(csv_file):
        os.remove(csv_file)

    spots_ddf = ddf.read_csv(
        "data/reverse_beacon_network/20220101.csv",
        dtype={"db": "float64", "freq": "float64", "speed": "float64"},
    )

    ak_indices = pd.read_csv(
        "data/SWPC/AK_values/prepped/202201AK.csv",
        dtype={"geomagnetic_dipole_lat": "object", "geomagnetic_dipole_long": "object"},
    )

    bar = Bar("Finished", max=len(spots_ddf))

    completed = 0

    spots_left = len(spots_ddf)
    spots_iter = spots_ddf.itertuples(name="Spot")

    futures = {}

    MAX_JOBS_IN_QUEUE = 4000

    while spots_left:

        for spot in spots_iter:
            future = client.submit(join_ak, spot, ak_indices)

            futures[future] = future

            for future in as_completed(futures):

                if os.path.exists(csv_file):
                    future.result().to_csv(
                        csv_file,
                        mode="a",
                        index=False,
                        header=False,
                    )
                else:
                    future.result().to_csv(
                        csv_file,
                        mode="w",
                        index=False,
                        header=True,
                    )

                del futures[future]
                spots_left -= 1
                bar.next()

    bar.finish()
