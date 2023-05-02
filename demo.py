from ids import *
import ids
import getpass
import json

# Open config
try:
    with open("config.json", "r") as f:
        CONFIG = json.load(f)
except FileNotFoundError:
    CONFIG = {}

def input_multiline(prompt):
    print(prompt)
    lines = []
    while True:
        line = input()
        if line == "":
            break
        lines.append(line)
    return "\n".join(lines)

def refresh_token():
    # If no username is set, prompt for it
    if "username" not in CONFIG:
        CONFIG["username"] = input("Enter iCloud username: ")
    # If no password is set, prompt for it
    if "password" not in CONFIG:
        CONFIG["password"] = getpass.getpass("Enter iCloud password: ")
    # If grandslam authentication is not set, prompt for it
    if "use_gsa" not in CONFIG:
        CONFIG["use_gsa"] = input("Use grandslam authentication? [y/N] ").lower() == "y"

    def factor_gen():
        return input("Enter iCloud 2FA code: ")

    CONFIG["user_id"], CONFIG["token"] = ids._get_auth_token(
        CONFIG["username"], CONFIG["password"], CONFIG["use_gsa"], factor_gen=factor_gen
    )

def refresh_cert():
    CONFIG["key"], CONFIG["auth_cert"] = ids._get_auth_cert(
        CONFIG["user_id"], CONFIG["token"]
    )

def create_connection(): 
    conn = apns.APNSConnection()
    token = conn.connect()
    #conn.filter(['com.apple.madrid'])
    CONFIG['push'] = {
        'token': b64encode(token).decode(),
        'cert': conn.cert,
        'key': conn.private_key
    }
    return conn

def restore_connection():
    conn = apns.APNSConnection(CONFIG['push']['key'], CONFIG['push']['cert'])
    conn.connect(True, b64decode(CONFIG['push']['token']))
    #conn.filter(['com.apple.madrid', 'com.apple.private.alloy.facetime.multi'])
    return conn

def refresh_ids_cert():
    info = {
        "uri": "mailto:" + CONFIG["username"],
        "user_id": CONFIG['user_id'],
    }

    resp = None
    try:
        if "validation_data" in CONFIG:
            resp = ids._register_request(
                CONFIG['push']['token'],
                info,
                CONFIG['auth_cert'],
                CONFIG['key'],
                CONFIG['push']['cert'],
                CONFIG['push']['key'],
                CONFIG["validation_data"],
            )
    except Exception as e:
        print(e)
        resp = None

    if resp is None:
        print(
            "Note: Validation data can be obtained from @JJTech, or intercepted using a HTTP proxy."
        )
        validation_data = (
            input_multiline("Enter validation data: ")
            .replace("\n", "")
            .replace(" ", "")
        )
        resp = ids._register_request(
            CONFIG['push']['token'],
            info,
            CONFIG['auth_cert'],
            CONFIG['key'],
            CONFIG['push']['cert'],
            CONFIG['push']['key'],
            validation_data,
        )
        CONFIG["validation_data"] = validation_data

    ids_cert = x509.load_der_x509_certificate(
        resp["services"][0]["users"][0]["cert"]
    )
    ids_cert = (
        ids_cert.public_bytes(serialization.Encoding.PEM).decode("utf-8").strip()
    )

    CONFIG["ids_cert"] = ids_cert


if not 'push' in CONFIG:
    print("No existing APNs credentials, creating new ones...")
    #print("No push conn")
    conn = create_connection()
else:
    print("Restoring APNs credentials...")
    conn = restore_connection()
print("Connected to APNs!")

if not 'ids_cert' in CONFIG:
    print("No existing IDS certificate, creating new one...")
    if not 'key' in CONFIG:
        print("No existing authentication certificate, creating new one...")
        if not 'token' in CONFIG:
            print("No existing authentication token, creating new one...")
            refresh_token()
        print("Got authentication token!")
        refresh_cert()
    print("Got authentication certificate!")
    refresh_ids_cert()
print("Got IDS certificate!")

# This is the actual lookup!
print("Looking up user...")
ids_keypair = ids.KeyPair(CONFIG['key'], CONFIG['ids_cert'])
resp = ids.lookup(conn, CONFIG['username'], ids_keypair, 'com.apple.madrid', ['mailto:textgpt@icloud.com'])
print("Got response!")
print(resp)

# Save config
with open("config.json", "w") as f:
    json.dump(CONFIG, f, indent=4)