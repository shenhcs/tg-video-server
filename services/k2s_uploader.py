#upload video to k2s
#set k2s folder
#set k2s access to premium
#get k2s link


import requests
import json
import dotenv
import os

dotenv.load_dotenv()

class K2SUploader:
    def __init__(self):
        self.access_token = os.getenv("MONEYBIZ_API_TOKEN")
        self.parent_id = os.getenv("POT_FOLDER_ID")
        self.base_url = "https://keep2share.cc/api/v2/"

    def get_folders_list(self):
        url = self.base_url + "getFoldersList"
        data = {"access_token": self.access_token, "parent": None, "offset": 0, "limit": 100}
        return requests.post(url, json=data).json()
    
    def update_file_properties(self, file_id, new_access="premium", new_parent=None):
        url = self.base_url + "updateFile"
        data = {
            "access_token": self.access_token,
            "id": file_id,
            "new_access": new_access,
            "new_parent": new_parent
        }
        return requests.post(url, json=data).json()
    
    def upload_file(self, file_path):
        """Upload a file to K2S and return the file link"""
        # First get upload form data
        url = self.base_url + "getUploadFormData"
        data = {"access_token": self.access_token}
        
        response = requests.post(url, json=data)
        form_data = response.json()
        
        # Extract needed values
        form_action = form_data['form_action']
        file_field = form_data['file_field']
        ajax = form_data['form_data']['ajax']
        params = form_data['form_data']['params']
        signature = form_data['form_data']['signature']

        # Prepare file upload
        files = {
            file_field: open(file_path, 'rb')
        }
        
        # Prepare form data
        upload_data = {
            'ajax': ajax,
            'signature': signature,
            'params': params
        }

        # Upload file
        upload_response = requests.post(
            form_action,
            files=files,
            data=upload_data
        )
        
        upload_result = upload_response.json()
        
        # Update file to premium access and move to correct folder
        self.update_file_properties(
            upload_result['user_file_id'],
            new_access="premium",
            new_parent=self.parent_id
        )

        # Return file link in format: https://k2s.cc/file/{file_id}
        return f"https://k2s.cc/file/{upload_result['user_file_id']}"
    
    def get_file_info(self, file_id):
        url = self.base_url + "getFile"
        data = {"access_token": self.access_token, "id": file_id}
        return requests.post(url, json=data).json() 
    
    def upload_file_to_folder_and_set_access(self, file_path, folder_id=None, new_access=None):
        file_info = self.upload_file(file_path, folder_id)
        update_response = self.update_file_properties(file_info['user_file_id'], new_access=new_access, new_parent=folder_id)
        return file_info, update_response





def get_folders_list(access_token):
    url = "https://keep2share.cc/api/v2/getFoldersList"
    
    # Updated request structure
    data = {
        "access_token": access_token,  # Changed from access_token to auth_token
        "parent": None,              # Changed from parent_id to parent
        "offset": 0,                 # Added required parameter
        "limit": 100                 # Added required parameter
    }
    
    headers = {
        'Content-Type': 'application/json'
    }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        print(f"Response Status: {response.status_code}")
        print(f"Response Content: {response.text}")
        
        if response.status_code == 200:
            folders = response.json()
            for folder in folders.get('folders', []):
                print(f"Folder Name: {folder.get('name')} | ID: {folder.get('id')}")
            return folders
    except requests.exceptions.RequestException as e:
        print(f"Error getting folders: {e}")
        return None


def update_file_properties(access_token, file_id, new_access="premium", new_parent=None):
    url = "https://keep2share.cc/api/v2/updateFile"
    
    # Ensure correct request structure
    data = {
        "access_token": access_token,  # Using access_token instead of auth_token
        "id": file_id,
        "new_access": new_access,
        "new_parent": new_parent
    }
    
    headers = {
        'Content-Type': 'application/json'
    }
    
    # Debug print
    print("Sending data:", json.dumps(data, indent=2))
    
    try:
        response = requests.post(url, headers=headers, json=data)
        print(f"Response Status: {response.status_code}")
        print(f"Response Content: {response.text}")
        
        # Check if response is JSON
        try:
            return response.json()
        except json.JSONDecodeError:
            print("Response is not JSON format")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"Error updating file: {e}")
        return None


def upload_to_keep2share(file_path, folder_id=None):
    # First API call to get upload form data
    headers = {'Content-Type': 'application/json'}
    data = {'access_token': os.getenv("MONEYBIZ_API_TOKEN")}
    


    # Get upload form data
    response = requests.post(
        'https://keep2share.cc/api/v2/getUploadFormData',
        headers=headers,
        json=data
    )
    form_data = response.json()
    print(form_data)    

    # Extract needed values
    form_action = form_data['form_action']
    file_field = form_data['file_field']
    ajax = form_data['form_data']['ajax']
    params = form_data['form_data']['params']
    signature = form_data['form_data']['signature']

    # Prepare file upload
    files = {
        file_field: open(file_path, 'rb')
    }
    
    # Prepare form data
    upload_data = {
        'ajax': ajax,
        'signature': signature,
        'params': params
    }

    print("form_action", form_action)

    # Upload file
    upload_response = requests.post(
        form_action,
        files=files,
        data=upload_data
    )
    
    # update file access to premium
    print(update_file_properties(os.getenv("MONEYBIZ_API_TOKEN"), upload_response.json()['user_file_id'], new_access="premium", new_parent=os.getenv("POT_FOLDER_ID")))


    # format: https://keep2share.cc/file/1234567890
    return upload_response.json()



# Usage upload rickroll
if __name__ == "__main__":
    file_path = "rickroll.mp4"

    token = os.getenv("MONEYBIZ_API_TOKEN")

    #print(get_folders_list(token))

    print(upload_to_keep2share("rickroll.mp4"))
