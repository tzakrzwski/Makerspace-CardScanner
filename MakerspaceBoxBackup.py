from box_sdk_gen import * #BoxClient, BoxOAuth, OAuthConfig, GetAuthorizeUrlOptions, BoxDeveloperTokenAuth, FileWithInMemoryCacheTokenStorage, 
from flask import Flask, request, redirect
from werkzeug.serving import make_server
import webbrowser, json, time
import os
import shutil
import threading
import datetime
import argparse

DEV_TOKEN = "NrFHccN9uqbwtrGRoFGQZgEJOTCedL9B" # From the Box dev console; Needs updated every hour
USE_DEV_TOKEN = False


'''
NOTE: Calling this file directly will generate a backup of the file requested (either user or login)


How often to update?
+ So, since clemson is on the enterprise plan, should be able to have 100 versions of documents before they start rolling over
+ However, to confirm logins between locations, should update the database more than one a week
+ But, weekly uploads also create the issue of the drive getting very cluttered with close to 52 files a very
+ However, tweleve files a very is not that bad...
+ Also, we have two different log types: user list and logins
+ Key:
\-> Back-up = Copy of file is stored
  > Updated = New version of file is stored or pulled
+ So, here is the proposal:
- One user list for all time; Backed-up ever week; Updated every minute*
- One login list per location per semester; Backed-up every week; Updated every day*
- * = Only update is there is new data
- Also, the system should check if there is a new user list periodicly and update its local copy if so

- Rn, there is not planned for any checks that there are duplicate users in the user list;
\-> System will just append the new ones to the end


Backups will be handled by windows tasks
OR linux cron jobs

Regular updates will be handled by main program


Updating shared Box files (user list)
1) Check if the file to update is locked
2) If locked, then try again later
3) If not locked, then lock the file to prevent someone else from updating
4) Download the current version of the file from box
5) Make the proper changes to the document (aka append new logins)


User list
+ Need two copies:
1) Master list from box
3) All local registration (for back-up)
+ When user registers, write to master list and local registrations
+ If the master list is locked, then wait for file to become unlocked

+ For our size of user database (~10,000), the file is actually pretty small (less one mb)
+ So can download, update, and push updated userlist without much pain

+ Also, would be nice to have a method to verify if the local registration has the same data as remote source



Authentication Notes:
+ Need to do via OAuth2 (otherwise need admin to aprove app)
\-> Therefore, an intern / user needs to login to authorize the system AND the system will act from their account
+ User / intern needs to have write access to the Makerspace Box to work
+ Can use a developer token, but needs refreshed every hour from the portal

+ OAuth2 "token" types:
+ Auth code -> returned from the OAuth2 workflow; Have to quickly use to exchange for an access token
+ Access token -> Authorization token that allows you to make requests on users behalf; Needs refreshed every hour
+ Refresh token -> Comes with each Access token; Can be exchanged for a new Access token; Good for 60 days, I believe
+ Process flow
\-> User OAuth2 -> Auth code -> Access token + Refresh Token
- Then after some time, Refresh Token -> Access token + Refresh Token
- Library handles the refresh token bit automatically

+ OAuth2 process:
1) Create BoxOAuth object -> has application ID / secret
2) Check if we already have a token cached
3) If token is not there / invalid, then generate authorization url
4) Open a webbrowser
5) Start a temperorary webserver and wait for user to authorize
6) Generate BoxClient
'''

# Read configuration options from file
with open("box_config.json") as f:
    config_options = json.loads(f.read())

'''
Works through the box authentication workflow to return a client object
'''
def get_box_client_oauth(allow_login = True) -> BoxClient:

    # Check if in development; Then use the development token
    if USE_DEV_TOKEN:

        # Use development token to generate the client (aka account of developer)
        print("Using developer token for Box Client")
        auth = BoxDeveloperTokenAuth(token=DEV_TOKEN)
        return BoxClient(auth=auth)
    
    # Create the box auth object with pararmeters for this application / storage of token
    auth = BoxOAuth(
        OAuthConfig(client_id=config_options["CLIENT_ID"],
                    client_secret=config_options["CLIENT_SECRET"],
                    token_storage=FileWithInMemoryCacheTokenStorage(config_options["CACHE_FILE"]),
                )
    )

    # Check if the token storage contains a valid token
    print("Checking for active access token")
    access_token = auth.token_storage.get()
    if not access_token and allow_login:

        # No token, so need to authorize the app via OAuth2
        print("No active access token, authorization required")

        # Create server to handle authorization workflow
        app = Flask(__name__)

        # Server callback functions
        # Redirect user to authorization site
        @app.route("/")
        def get_auth():
            auth_url = auth.get_authorize_url(options=GetAuthorizeUrlOptions(redirect_uri=config_options["REDIRECT_URI"]))
            return redirect(auth_url, code=302)

        # Callback when user has authorized the app
        @app.route("/callback")
        def callback():
            nonlocal OAuth2_Complete
            print("Help me")

            # Get authorization token from auth code
            auth.get_tokens_authorization_code_grant(request.args.get("code"))

            # Set flag for main process that OAuth2 is complete
            OAuth2_Complete = True
            return "Authorization Complete; Please close window"
        
        # Server Thread (mainly used to kill the thread when we are done)
        # https://stackoverflow.com/questions/15562446
        class ServerThread(threading.Thread):

            def __init__(self, host, port, app: Flask):
                threading.Thread.__init__(self)
                self.server = make_server(host, port, app)
                self.ctx = app.app_context()
                self.ctx.push()

            def run(self):
                self.server.serve_forever()

            def shutdown(self):
                self.server.shutdown()

        OAuth2_Complete = False

        # Start server
        server = ServerThread(config_options["CALLBACK_HOSTNAME"], config_options["CALLBACK_PORT"], app)
        server.start()

        # Open webbrowser to server
        webbrowser.open("http://"+config_options["CALLBACK_HOSTNAME"]+":"+config_options["CALLBACK_PORT"])

        # Wait until server has completed OAuth2 process
        while True:
            if OAuth2_Complete:
                # Wait for the user to see webpage
                time.sleep(2)
                break

        # Close the server
        server.shutdown()
        server.join()

    # Double check that we now have a valid token
    access_token = auth.token_storage.get()
    if not access_token:
        raise Exception("Unable to get access token")
    
    print("Access token active")

    # Return Box Client 
    return BoxClient(auth=auth)

'''
Parent class for handling box files
'''
class BoxFile():

    # Need to pass either a path OR a file_name
    # Also, need to either pass a folder_id or file_id
    def __init__(self, client:BoxClient, local_path, folder_id = None, file_id = None, box_overwrite = False):

        self.box_overwrite = box_overwrite # Used to prevent object from creating new files that overwrite existing ones in box
        # Note, this setting only applies for new files being generated with the same filename
        # Does not apply if you specify the file_id
        # Meant as a safety measure; Can disable

        self.lock_held = False # Stores if object has lock to file; Set to timestamp of lock experation when lock set
        self.client = client # For brokering deals with box

        # Check if the file in the local path already exsists
        if os.path.isfile(local_path):
            self.local_path = os.path.abspath(local_path) # Path to local file
            self.file_name = os.path.basename(local_path) # Name of the file

        # Check if the directory in the local path exists
        elif os.path.isdir(os.path.dirname(local_path)):
            self.local_path = os.path.abspath(local_path) # Path to local file
            self.file_name = os.path.basename(local_path) # Name of the file
            
        # The file does not exsist and neither does the parent directory
        else:
            raise Exception(f"Local path {local_path} does not exist, nor directory {os.path.dirname(local_path)}")

        # Setup remote storage
        # Check if file id provided
        if file_id:
            self.file_id = file_id # Box id for the file

            # Get info about the box file
            self.box_file_info = client.files.get_file_by_id(self.file_id)
            print(f"Box file found: {self.box_file_info.name}")

            # Record file parent folder
            self.folder_id = self.box_file_info.parent.id # Box if for parent folder of file (required for uploads / updates)
        
        # Check if folder id provided
        elif folder_id:
            
            # Check if folder exists
            folder_info = client.folders.get_folder_by_id(folder_id)
            print(f"Box folder found: {folder_info.name}")

            # Perform an inital upload to box
            self.folder_id = folder_id
            self.upload()

        # Neither folder or file provided; 
        else:
            raise Exception(f"No box file or box folder provided")


    '''
    Uploads new file to box
    https://github.com/box-community/box-python-gen-workshop/blob/main/workshops/files/files.md
    '''
    def upload(self):

        # Check if there the file exists on the local machine
        if os.path.exists(self.local_path):
            file_mode = "rb"
        # File does not yet exist; Create local file when upload
        else:
            file_mode = "wb"

        try:
            # Perform "preflight check" -> aka can the file be uploaded
            self.client.uploads.preflight_file_upload_check(
                name=self.file_name,
                parent=PreflightFileUploadCheckParent(id=self.folder_id)
                )
            
            # Create new file in folder
            uploaded_files = self.client.uploads.upload_file(
                UploadFileAttributes(self.file_name, parent=UploadFileAttributesParentField(self.folder_id)),
                file=open(self.local_path, file_mode)
                )
            
            # Get info about the box file
            self.box_file_info = uploaded_files.entries[0]
            self.file_id = uploaded_files.entries[0].id
            print(f"Box file Uploaded: {self.box_file_info.name}")

        except BoxAPIError as err:
            # File is not able to be uploaded
            # Check if the error is due to filename conflict
            if err.response_info.body.get("code", None) == "item_name_in_use":

                # Check if box overwrite is enabled; If so, then throw error
                if not self.box_overwrite:
                    raise err
                
                # File already exists, so get the file id
                self.file_id = err.response_info.body["context_info"]["conflicts"]["id"]

                # Update (overwrite) file in box
                uploaded_files = self.client.uploads.upload_file_version(
                    self.file_id,
                    UploadFileAttributes(self.file_name, UploadFileAttributesParentField(self.folder_id)),
                    file=open(self.local_path, file_mode)
                    )

                # Get info about the box file
                self.box_file_info = uploaded_files.entries[0]
                print(f"Box file already exists: {self.box_file_info.name}; File overwritten")
    

    '''
    Update the file on box
    Return: 1 if sucessful; 0 otherwise
    '''
    def update_remote(self):

        # Check if this file object does not hold the lock
        if not self.islockheld():

            # Check if file is locked (aka another computer is in control)
            file_lock_info = self.client.files.get_file_by_id(
                self.file_id,
                fields=["lock"]
                )
            if file_lock_info.lock:
                raise Exception(f"File {self.file_name} is locked; Not safe to update")
        
        # Lock the file during upload to prevent conflict
        self.lock()
        
        # Update file in box
        uploaded_files = self.client.uploads.upload_file_version(
            self.file_id,
            UploadFileAttributes(self.file_name, UploadFileAttributesParentField(self.folder_id)),
            file=open(self.local_path, "rb")
            )
        
        # Update the box file information
        self.box_file_info = self.client.files.get_file_by_id(self.file_id)
        
        # Unlocks the file
        self.unlock()
        
        return 1


    '''
    Create a lock on a file during updating to prevent conflicts
    '''
    def lock(self, time=10):

        # Calculate the time for the lock to be active till    
        expiration_time = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=time)

        # Set the lock
        self.client.files.update_file_by_id(
            self.file_id,
            lock=UpdateFileByIdLock(expires_at=expiration_time)
            )
        
        # Record the expiration_time (to determine if the object still owns lock)
        self.lock_held = expiration_time
        
        return 1
    
    '''
    Checks if this object holds the lock to the file
    Returns: 1 if object holds lock; 0 if not holds lock
    '''
    def islockheld(self):
        return (self.lock_held is not False and self.lock_held > datetime.datetime.now(datetime.timezone.utc))


    '''
    Remove the lock on the file 
    '''
    def unlock(self):

        # Check if the current object holds the file lock
        if not self.islockheld():

            # Check if file is locked by another process
            file_lock_info = self.client.files.get_file_by_id(
                self.file_id,
                fields=["lock"]
                )
            if file_lock_info.lock:
                raise Exception(f"File {self.file_name} is locked; Not safe to update")
            
        # Update box file to remove lock
        self.client.files.update_file_by_id(
            self.file_id,
            lock=null
            )
        
        # Clear object holding lock
        self.holds_lock = False

        return 1

    '''
    Download file from box
    https://github.com/box-community/box-python-gen-workshop/blob/main/workshops/files/files.md
    '''
    def download(self):

        # Download file from box
        file_stream = self.client.downloads.download_file(self.file_id)

        # Open the local file and copy the filedata
        with open(self.local_path, "wb") as file:
            shutil.copyfileobj(file_stream, file)

        return 1


'''
Box File object for handling the master user list
'''
class BoxFileUserList(BoxFile):

    # Need to pass path to local file and remote file id
    def __init__(self, client:BoxClient, local_path, file_id, update_interval=60):
        
        self.update_interval = update_interval # How often to check box for a new version of the file

        # Call parent initalization to create the box object
        super().__init__(client, local_path=local_path, file_id=file_id, box_overwrite=False)

        # Download the current version of the user list from remote
        self.download()

        # Create and start a thread for checking for updates to the box file
        self.poll_remote_thread = threading.Thread(target=self.poll_remote, daemon=True)
        self.poll_remote_thread.start()

    '''
    Check the box file for a new version
    Return: 1 if updated file, 0 if no update, -1 if error
    '''
    def check_remote_updates(self):
        
        # Get info about the box file
        current_box_file_info = self.client.files.get_file_by_id(self.file_id)
        
        # Check for difference between file versions
        if current_box_file_info.file_version.id != self.box_file_info.file_version.id:

            # Difference in file version; Download the latest version
            self.download()

            # Update the box file information
            self.box_file_info = self.client.files.get_file_by_id(self.file_id)

            return 1
        
        # Current box file has same version as local
        else:
            return 0 


    '''
    Periodicly checks remote source for updates to box file
    '''
    def poll_remote(self):
        
        # Wrap function in exception handling to prevent from stopping thread
        try:

            # Loop forever
            # Note, since this is called from a daemon thread, it will be ended when main thread exited
            while True:
                
                # Check for updates to the box file
                if self.check_remote_updates(self.client) == 1:
                    print("Remote updated and Local updated")

                # Wait for the update interval before polling again
                time.sleep(self.update_interval)
                # And yes, technically I could use a timestamp for this to get more accurate polling times
                # Or a sceduler, but tbh, its not that deep

        except Exception as err:
            print(f"Polling thread rose exception: {err}")


    '''
    Write a new entry to the local and remote userbase
    '''
    def write_user_entry(self, entry:List[str]):

        # Check if the current object holds the file lock
        if not self.islockheld():

            # Check if file is locked (aka another computer is in control)
            file_lock_info = self.client.files.get_file_by_id(
                self.file_id,
                fields=["lock"]
                )
            if file_lock_info.lock:
                raise Exception(f"File {self.file_name} is locked; Not safe to update")
        
        # Lock the file during update to prevent collsions
        self.lock(self.client, time=60)

        # Check if there are updates to the remote source
        self.check_remote_updates(self.client)

        # Open the local file and write the new entry
        with open(self.local_path, "a") as file:
            file.write(','.join(entry)+'\n')

        # Update the remote file
        self.update_remote(self.client)

        # Updating the file will also remove the lock 

        return 1


'''
Box File object for creating a backup of the given Box File object
'''
class BoxFileBackup(BoxFile):

    # Need to pass path to file for backup as well as the folder for creating the backup
    def __init__(self, client:BoxClient, file_path, backup_path, folder_id, backup_extension = ""):

        # Check if the file and backup path are valid
        if not os.path.exists(file_path) or not os.path.isfile(file_path):
            raise Exception("Local path does not exist; Please provide filepath")
        if not os.path.exists(backup_path) or not os.path.isdir(backup_path):
            raise Exception("Backup path does not exist; Please provide directory path")
        
        # Check if backup_extension is provided
        if not backup_extension:

            # Generate extension from current timestamp
            backup_extension = "_" + datetime.datetime.now().strftime("%Y%m%d_%H%M")

        # Generate filename for backup
        basename = os.path.basename(file_path)
        basename_split = os.path.splitext(basename)
        backup_file_path = os.path.join(backup_path, basename_split[0]+backup_extension+basename_split[1])
        
        # Create the backup of the target file
        shutil.copy2(file_path, backup_file_path)

        # Call parent initalization to create the box object
        super().__init__(client, local_path=backup_file_path, folder_id=folder_id)

        # This function will create the remote back of the file
        # Now, object will behave like standard box file object



'''
Box File object for handling the login records
NOTE: The files from this source on box are really just copies of the ones from the local
\-> Its the responsiblity of the local machine (and maintainers) to not overwrite remote and local data
'''
class BoxFileLoginList(BoxFile):

    '''
    Write a new entry to the local login file
    '''
    def write_login_entry(self, entry:List[str]):

        # Open the local file and write the new entry
        with open(self.local_path, "a") as file:
            file.write(','.join(entry)+'\n')



'''
Main Process Loop
Processes system arguements to generate a backup of the requested file type
'''
def main():

    # Process the input argument of the file type to backup
    parser = argparse.ArgumentParser()
    parser.add_argument("file_type",
                        help="Type of file to backup: Either 'login' or 'user'",
                        type=str)
    args = parser.parse_args()

    # Branch based what file type to backup
    if args.file_type == "login":

        # Get the client infomation for the backup
        # Note, there needs to be an active token on file OR the function will fail
        client = get_box_client_oauth(allow_login=False)
        
        # Create a backup of the configured login file
        backupFile = BoxFileBackup(client,
                                   config_options["LOGIN_FILE_PATH"],
                                   config_options["BACKUP_FOLDER_PATH"], 
                                   config_options["BACKUP_BOX_FOLDER_ID"]
                                   )

        print(f"Created backup of file: {config_options["LOGIN_FILE_PATH"]} as {backupFile.file_name}")
        print(f"Remote file id: {backupFile.file_id}")

        return 1

    elif args.file_type == "user":
        
        # Get the client infomation for the backup
        # Note, there needs to be an active token on file OR the function will fail
        client = get_box_client_oauth(allow_login=False)
        
        # Create a backup of the configured user file
        backupFile = BoxFileBackup(client,
                                   config_options["USER_FILE_PATH"],
                                   config_options["BACKUP_FOLDER_PATH"], 
                                   config_options["BACKUP_BOX_FOLDER_ID"]
                                   )

        print(f"Created backup of file: {config_options["USER_FILE_PATH"]} as {backupFile.file_name}")
        print(f"Remote file id: {backupFile.file_id}")

        return 1

    else:
        # Not a valid parameter provided; Throw error
        raise Exception(f"Not a valid parameter for file backup: {args.file_type}")




def test():
    client = get_box_client_oauth()
    boxFile = BoxFile(client, local_path="box_testing/test_data_250304.csv", folder_id="309828162730", box_overwrite=True)
    print("Object Created")
    boxFile.download()
    print("File downloaded")

    with open(boxFile.local_path, "a") as f:
        f.write(f"tzakrw,2068295,{str(datetime.datetime.now())}\n")

    print("Wrote to file")
    
    boxFile.update_remote()

    print("Updated file")

    boxbackup = BoxFileBackup(client, "box_testing/test_data.csv", "box_testing/backup", "309962394982")

    boxuserlist = BoxFileUserList(client, file_id="1793836084373", local_path="box_testing/test_data_250304.csv", update_interval=60)

    entry = ["tzakrzw","908787","CECAS","Mechanical Engineering","Senior", str(datetime.datetime.now()),"3/3/2025 11:35","999"]
    boxuserlist.write_user_entry(entry)

    print(f'Added entry to log: {','.join(entry)}')

    time.sleep(30)

    boxFile = BoxFile(client, file_id="1792496802284", local_path="box_testing/test_data_250304.csv")

    with open(boxFile.local_path, "a") as f:
        f.write(f"tzakrw,2068295,{str(datetime.datetime.now())}\n")

    boxFile.update_remote()
    print("Wrote some extra data to file")

    time.sleep(60)


    

if __name__ == '__main__':
    main()
    