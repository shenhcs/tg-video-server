import requests
import json
import dotenv
import os

dotenv.load_dotenv()

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

    return upload_response.json()



# Usage upload rickroll
if __name__ == "__main__":
    file_path = "rickroll.mp4"

    token = os.getenv("MONEYBIZ_API_TOKEN")

    #print(get_folders_list(token))

    print(upload_to_keep2share("rickroll.mp4"))
