# Import the necessary modules
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import pandas as pd

# Function to list all folders recursively
def list_folders(service, parent):
    # List all folders under the parent
    folders = service.folders().list(parent=parent).execute().get('folders', [])
    for folder in folders:
        print(f"Processing folder: {folder['name']}")
        # Recursively list all sub-folders
        folders.extend(list_folders(service, folder['name']))
    return folders

# Function to list all projects under a parent
def list_projects(service, parent):
    try:
        return service.projects().list(filter=f'parent.id:{parent.split("/")[-1]}').execute().get('projects', [])
    except HttpError as error:
        # Skip any parents that we cannot access or do not exist
        if error.resp.status in [403, 404]:
            print(f"Cannot access or find parent: {parent}. Skipping...")
            return []
        else:
            raise

# Function to list all instances in a project
def list_instances(compute, project_id):
    try:
        instances = []
        request = compute.instances().aggregatedList(project=project_id)
        while request is not None:
            response = request.execute()
            for zone, instances_scoped_list in response['items'].items():
                if 'instances' in instances_scoped_list:
                    for instance in instances_scoped_list['instances']:
                        instance['project'] = project_id
                        instance['zone'] = zone.split('/')[-1]
                        instances.append(instance)
            # Get the next page of instances, if any
            request = compute.instances().aggregatedList_next(previous_request=request, previous_response=response)
        return instances
    except HttpError as error:
        # Skip any projects that we cannot access or do not exist
        if error.resp.status in [403, 404]:
            print(f"Cannot access or find project: {project_id}. Skipping...")
            return []
        else:
            raise

# Main function to tie it all together
def main():
    # Path to your service account key file
    key_path = "/PATH/TO/YOUR/JSON/XXXXX.json"
    # Load credentials from the service account file
    credentials = service_account.Credentials.from_service_account_file(key_path)

    # Build services for Cloud Resource Manager v1 and v2, and Compute
    cloudresourcemanager_v1 = build('cloudresourcemanager', 'v1', credentials=credentials)
    cloudresourcemanager_v2 = build('cloudresourcemanager', 'v2', credentials=credentials)
    compute = build('compute', 'v1', credentials=credentials)

    # Replace this with your org id
    org_id = 'XXXXXX'

    instances_data = []
    parent = f"organizations/{org_id}"
    # List all folders (including sub-folders)
    folders = list_folders(cloudresourcemanager_v2, parent)
    # Include the root org as a "folder"
    folders.append({'name': parent})

    for folder in folders:
        # List all projects under each folder
        projects = list_projects(cloudresourcemanager_v1, folder['name'])
        for project in projects:
            # List all instances in each project
            instances = list_instances(compute, project['projectId'])
            for instance in instances:
                # Collect data for each instance
                instances_data.append({
                    'Instance ID': instance['id'],
                    'Project ID': instance['project'],
                    'Name': instance['name'],
                    'Zone': instance['zone'],
                    'Machine type': instance['machineType'].split('/')[-1],
                    'Internal IP': instance['networkInterfaces'][0]['networkIP'],
                    'External IP': instance['networkInterfaces'][0]['accessConfigs'][0]['natIP'] if 'accessConfigs' in instance['networkInterfaces'][0] and 'natIP' in instance['networkInterfaces'][0]['accessConfigs'][0] else 'none',
                    'Labels': instance.get('labels', 'none'),
                    'Network Tags': ', '.join(instance.get('tags', {}).get('items', []))
                })

    # Create a DataFrame from the instance data and save it to an Excel file
    df = pd.DataFrame(instances_data)
    df.to_excel('gcp_instances_info.xlsx', index=False)

if __name__ == '__main__':
    main()
