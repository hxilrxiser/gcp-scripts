from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import pandas as pd

def list_folders(service, parent):
    folders = service.folders().list(parent=parent).execute().get('folders', [])
    for folder in folders:
        print(f"Processing folder: {folder['name']}")
        folders.extend(list_folders(service, folder['name']))
    return folders

def list_projects(service, parent):
    try:
        return service.projects().list(filter=f'parent.id:{parent.split("/")[-1]}').execute().get('projects', [])
    except HttpError as error:
        if error.resp.status in [403, 404]:
            print(f"Cannot access or find parent: {parent}. Skipping...")
            return []
        else:
            raise

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
            request = compute.instances().aggregatedList_next(previous_request=request, previous_response=response)
        return instances
    except HttpError as error:
        if error.resp.status in [403, 404]:
            print(f"Cannot access or find project: {project_id}. Skipping...")
            return []
        else:
            raise

def main():
    # Path to your service account key file
    key_path = "/PATH/TO/YOUR/JSON/XXXXX.json"
    credentials = service_account.Credentials.from_service_account_file(key_path)

    cloudresourcemanager_v1 = build('cloudresourcemanager', 'v1', credentials=credentials)
    cloudresourcemanager_v2 = build('cloudresourcemanager', 'v2', credentials=credentials)
    compute = build('compute', 'v1', credentials=credentials)

    org_id = 'XXXXXX'  # Replace this with your org id

    instances_data = []
    parent = f"organizations/{org_id}"
    folders = list_folders(cloudresourcemanager_v2, parent)
    folders.append({'name': parent})  # Include the root org as a "folder"

    for folder in folders:
        projects = list_projects(cloudresourcemanager_v1, folder['name'])
        for project in projects:
            instances = list_instances(compute, project['projectId'])
            for instance in instances:
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

    df = pd.DataFrame(instances_data)
    df.to_excel('gcp_instances_info.xlsx', index=False)

if __name__ == '__main__':
    main()
