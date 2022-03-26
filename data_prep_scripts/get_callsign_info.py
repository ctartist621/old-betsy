import asyncio
import os

import aiofiles
# import aiofiles.os as os
import aiohttp
import pandas as pd
import untangle
from aiohttp import ClientSession
from progress.bar import Bar

username = os.getenv("HAMQTH_USERNAME")
password = os.getenv("HAMQTH_PASSWORD")
api_root = "https://www.hamqth.com/xml.php"
auth_uri = f"{api_root}?u={username}&p={password}"
data_dir = "data/hamqth"


# Get HamQTH Session ID
document = untangle.parse(auth_uri)
session_id = document.HamQTH.session.session_id.cdata


async def fetch_html(url: str, session: ClientSession, **kwargs) -> str:
    """GET request wrapper to fetch page HTML.

    kwargs are passed to `session.request()`.
    """

    resp = await session.request(method="GET", url=url, **kwargs)
    resp.raise_for_status()
    # logger.info("Got response [%s] for URL: %s", resp.status, url)
    html = await resp.text()
    return html


def callsign_to_filename(callsign: str) -> str:
    keepcharacters = (" ", ".", "_")
    clean_callsign = "".join(
        c for c in callsign if c.isalnum() or c in keepcharacters
    ).rstrip()
    return clean_callsign


async def get_gridsquare_for_callsign(
    bar, session: ClientSession, callsign_to_lookup: str
) -> str:
    if (
        isinstance(callsign_to_lookup, str)
        and not callsign_to_lookup.isnumeric()
        and not isinstance(callsign_to_lookup, float)
    ):
        if os.path.exists(f"{data_dir}/{callsign_to_filename(callsign_to_lookup)}.xml"):
            # print("Skipping, stored result: ", callsign_to_lookup)
            pass
        else:

            try:
                callsign_lookup_uri = f"{api_root}?id={session_id}&callsign={callsign_to_lookup}&prg=old-betsy"
                resp = await fetch_html(callsign_lookup_uri, session)

                decoded_xml = resp
                callsign_result = untangle.parse(decoded_xml)
                if hasattr(callsign_result.HamQTH, "session") and hasattr(
                    callsign_result.HamQTH.session, "error"
                ):
                    error_message = f"\nError retrieving callsign '{callsign_to_lookup}': {callsign_result.HamQTH.session.error.cdata}"
                    print(error_message)
                    # raise Exception(error_message)

                else:
                    # print("Found Callsign: ", callsign_to_lookup)

                    os.makedirs(data_dir, exist_ok=True)
                    async with aiofiles.open(
                        f"{data_dir}/{callsign_to_filename(callsign_to_lookup)}.xml",
                        "w",
                    ) as f:
                        await f.write(decoded_xml)
                        await f.close()
            except:
                pass

    bar.next()


async def retrieve_callsigns(spots_file):
    spots_pd = pd.read_csv(
        spots_file,
        dtype={"db": "float64", "freq": "float64", "speed": "float64"},
    )

    # spots_pd = spots_pd.sample(100)

    with Bar("Processing", max=len(spots_pd) * 2) as bar:
        async with ClientSession() as session:
            tasks = []

            for spot in spots_pd.itertuples(name="Spot"):
                tasks.append(get_gridsquare_for_callsign(bar, session, spot.callsign))
                tasks.append(get_gridsquare_for_callsign(bar, session, spot.dx))

            await asyncio.gather(*tasks)
            bar.finish()


asyncio.run(retrieve_callsigns("data/reverse_beacon_network/20220101.csv"))
