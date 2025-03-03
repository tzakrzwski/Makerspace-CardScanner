from box_sdk_gen import BoxClient, BoxOAuth, OAuthConfig, GetAuthorizeUrlOptions, BoxDeveloperTokenAuth
from flask import Flask, request, redirect
import webbrowser

DEV_TOKEN = "Ni5P7o1Ym4Lkq40NHEcsYp0pI3DAGNlq" # From the Box dev console; Needs updated every hour
CLIENT_ID = "how4zojj7mde1i0ntcs448k7k3xfbx4h"
CLIENT_SECRET = "SOxonuMF0Nk9hUXbrdLy8z99vjrgOfse"


app = Flask(__name__)

AUTH = BoxOAuth(
    OAuthConfig(client_id=CLIENT_ID, client_secret=CLIENT_SECRET)
)



@app.route("/")
def get_auth():
    auth_url = AUTH.get_authorize_url(
        options=GetAuthorizeUrlOptions(redirect_uri="http://127.0.0.1:4999/callback")
    )
    return redirect(auth_url, code=302)


@app.route("/callback")
def callback():
    print("The callback")

    AUTH.get_tokens_authorization_code_grant(request.args.get("code"))
    client = BoxClient(auth=AUTH)

    items_in_root_folder = [
        item.name for item in client.folders.get_folder_items(folder_id="0").entries
    ]

    print(", ".join(items_in_root_folder))
    return ", ".join(items_in_root_folder)



def main(token: str):
    auth: BoxDeveloperTokenAuth = BoxDeveloperTokenAuth(token=token)
    client: BoxClient = BoxClient(auth=auth)
    for item in client.folders.get_folder_items('0').entries:
        print(item.name)


    

if __name__ == '__main__':
    main(DEV_TOKEN)
    webbrowser.open("http://127.0.0.1:4999")
    app.run(host="127.0.0.1", port=4999)
    