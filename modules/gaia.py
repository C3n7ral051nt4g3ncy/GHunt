#!/usr/bin/env python3

import json
import sys
import os
from datetime import datetime
from io import BytesIO
from os.path import isfile
from pathlib import Path
from pprint import pprint

import httpx
from PIL import Image
from geopy.geocoders import Nominatim

import config
from lib.banner import banner
import lib.gmaps as gmaps
import lib.youtube as ytb
from lib.utils import *


def gaia_hunt(gaiaID):
    banner()

    if not gaiaID:
        exit("Please give a valid GaiaID.\nExample : 113127526941309521065")

    if not isfile(config.data_path):
        exit("Please generate cookies and tokens first, with the check_and_gen.py script.")

    internal_auth = ""
    internal_token = ""

    cookies = {}

    with open(config.data_path, 'r') as f:
        out = json.loads(f.read())
        internal_auth = out["internal_auth"]
        internal_token = out["keys"]["internal"]
        cookies = out["cookies"]

    client = httpx.Client(cookies=cookies, headers=config.headers)

    account = get_account_data(client, gaiaID, internal_auth, internal_token, config)
    if not account:
        exit("[-] No account linked to this Gaia ID.")

    is_within_docker = within_docker()
    if is_within_docker:
        print("[+] Docker detected, profile pictures will not be saved.")

    geolocator = Nominatim(user_agent="nominatim")

    # get name & other info
    name = account["name"]
    if name:
        print(f"Name : {name}")

    if organizations := account["organizations"]:
        print(f"Organizations : {organizations}")

    if locations := account["locations"]:
        print(f"Locations : {locations}")

    if (
        profile_pic_url := account.get("profile_pics")
        and account["profile_pics"][0].url
    ):
        req = client.get(profile_pic_url)

        # TODO: make sure it's necessary now
        profile_pic_img = Image.open(BytesIO(req.content))
        profile_pic_flathash = image_hash(profile_pic_img)
        if is_default_profile_pic := detect_default_profile_pic(
            profile_pic_flathash
        ):
            print("\n[-] Default profile picture")

        else:
            print("\n[+] Custom profile picture !")
            print(f"=> {profile_pic_url}")
            if config.write_profile_pic and not is_within_docker:
                open(Path(config.profile_pics_dir) / f'{gaiaID}.jpg', 'wb').write(req.content)
                print("Profile picture saved !")
    # cover profile picture
    cover_pic = account.get("cover_pics") and account["cover_pics"][0]
    if cover_pic and not cover_pic.is_default:
        req = client.get(cover_pic_url)

        print("\n[+] Custom profile cover picture !")
        print(f"=> {cover_pic_url}")
        if config.write_profile_pic and not is_within_docker:
            open(Path(config.profile_pics_dir) / f'cover_{email}.jpg', 'wb').write(req.content)
            print("Cover profile picture saved !")


    print(f"\nGaia ID : {gaiaID}")

    if emails := account["emails_set"]:
        print(f"Contact emails : {', '.join(map(str, emails.values()))}")

    if phones := account["phones"]:
        print(f"Contact phones : {phones}")

    # check YouTube
    if name:
        confidence = None
        if data := ytb.get_channels(
            client, name, config.data_path, config.gdocs_public_doc
        ):
            confidence, channels = ytb.get_confidence(data, name, profile_pic_flathash)

            if confidence:
                print(f"\n[+] YouTube channel (confidence => {confidence}%) :")
                for channel in channels:
                    print(f"- [{channel['name']}] {channel['profile_url']}")
                if possible_usernames := ytb.extract_usernames(channels):
                    print("\n[+] Possible usernames found :")
                    for username in possible_usernames:
                        print(f"- {username}")
            else:
                print("\n[-] YouTube channel not found.")

        else:
            print("\n[-] YouTube channel not found.")
    if reviews := gmaps.scrape(
        gaiaID,
        client,
        cookies,
        config,
        config.headers,
        config.regexs["review_loc_by_id"],
        config.headless,
    ):
        confidence, locations = gmaps.get_confidence(geolocator, reviews, config.gmaps_radius)
        print(f"\n[+] Probable location (confidence => {confidence}) :")

        loc_names = [
            f"- {loc['avg']['town']}, {loc['avg']['country']}"
            for loc in locations
        ]

        loc_names = set(loc_names)  # delete duplicates
        for loc in loc_names:
            print(loc)
