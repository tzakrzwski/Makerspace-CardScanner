from datetime import datetime


# Path to excel sheet
file_path = "hardware_users.xlsx"
sheet_name = "Scans"
sheet2_name ="Users"

# Constants
Location= "Watt"


'''
Container for passing data about a login
'''
class LoginEntry():

    def __init__(self, username:str=None, hardware_id=None, bypass_registration=0):
        
        self.username = username # Username for the login
        self.hardware_id = hardware_id # Card number for the user
        self.timestamp = datetime.now().strftime('%m/%d/%Y %H:%M:%S') # Timestamp of the Login
        self.bypass_registration = bypass_registration # Used to disable the registration / lookup procedure if the user has input an email

        # Search for the user in database
        self.new_user = self.search_user()


    """
    Searches the database for the user based on the input data
    Fills in missing data if present (username OR hardware_id)
    Returns 1 if user is already in database
    Returns 0 if user is not present in database
    """
    def search_user(self):
        pass
        

    """
    Returns if the user needs to register (aka needs to capture username)
    """
    def is_registered(self):
        if self.username or self.bypass_registration:
            return 1
        else:
            return 0
        


# Need new function for finding users -> should auto-call on generation
# Should take both username and hardware_id as input and provide the missing data
# Should also return if the user is new (we don't have their hardware id)
# Should check if we have the directory info for the user
# -- If we don't, then have the option to have them manually enter